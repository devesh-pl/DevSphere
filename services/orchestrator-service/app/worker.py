"""RabbitMQ worker with leases, heartbeats and fenced completion."""

import json
import logging
import threading

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import update

from app.core.broker import declare_queue, open_connection
from app.core.config import settings
from app.core.provisioning import provision_project
from app.core.recovery_config import (
    MAX_OPERATION_ATTEMPTS,
    OPERATION_LEASE_SECONDS,
    WORKER_HEARTBEAT_SECONDS,
)
from app.database.session import get_db
from app.models.operation import Operation


logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("devsphere.orchestrator.worker")


def utc_now():
    return datetime.now(timezone.utc)


def renew_lease(operation_id, attempt, stop_event):
    """Refresh lease using an independent database session."""

    while not stop_event.wait(WORKER_HEARTBEAT_SECONDS):
        generator = get_db()
        db = next(generator)

        try:
            now = utc_now()

            result = db.execute(
                update(Operation)
                .where(
                    Operation.id == operation_id,
                    Operation.status == "running",
                    Operation.attempt_count == attempt,
                    Operation.lease_expires_at > now,
                )
                .values(
                    lease_expires_at=(
                        now + timedelta(
                            seconds=OPERATION_LEASE_SECONDS
                        )
                    ),
                    last_heartbeat_at=now,
                )
                .execution_options(synchronize_session=False)
            )

            db.commit()

            if result.rowcount != 1:
                logger.warning(
                    "Lease no longer owned: %s",
                    operation_id,
                )
                return

        except Exception:
            db.rollback()
            logger.exception(
                "Heartbeat failed: %s",
                operation_id,
            )

        finally:
            generator.close()


def process_operation(operation_id):
    """Claim and process one operation with attempt fencing."""

    generator = get_db()
    db = next(generator)

    stop_event = threading.Event()
    heartbeat = None

    try:
        now = utc_now()

        claim = db.execute(
            update(Operation)
            .where(
                Operation.id == operation_id,
                Operation.status.in_(["pending", "queued"]),
                Operation.attempt_count < MAX_OPERATION_ATTEMPTS,
            )
            .values(
                status="running",
                attempt_count=Operation.attempt_count + 1,
                lease_expires_at=(
                    now + timedelta(
                        seconds=OPERATION_LEASE_SECONDS
                    )
                ),
                last_heartbeat_at=now,
                error_message=None,
            )
            .execution_options(synchronize_session=False)
        )

        db.commit()

        if claim.rowcount != 1:
            logger.info(
                "Operation not claimable: %s",
                operation_id,
            )
            return

        operation = db.get(Operation, operation_id)

        attempt = operation.attempt_count
        operation_type = operation.operation_type
        owner_id = operation.owner_id
        request_payload = operation.request_payload

        logger.info(
            "Claimed operation %s, attempt %s",
            operation_id,
            attempt,
        )

        heartbeat = threading.Thread(
            target=renew_lease,
            args=(operation_id, attempt, stop_event),
            daemon=True,
        )
        heartbeat.start()

        outcome = "completed"
        result_data = None

        try:
            if operation_type == "ping":
                result_data = {
                    "message": "pong",
                    "worker": "orchestrator-worker",
                }

            elif operation_type == "provision_project":
                result_data = provision_project(
                    operation_id,
                    owner_id,
                    request_payload,
                )

            else:
                raise ValueError("Unsupported operation type")

        except Exception:
            logger.exception(
                "Operation execution failed: %s",
                operation_id,
            )
            outcome = "failed"

        finally:
            stop_event.set()
            heartbeat.join(timeout=5)

        # Completion is conditional on the original claim.
        # A recovered or expired attempt cannot overwrite
        # a newer attempt's database state.
        now = utc_now()

        values = {
            "status": outcome,
            "lease_expires_at": None,
        }

        if outcome == "completed":
            values["result"] = json.dumps(result_data)
            values["error_message"] = None
        else:
            values["error_message"] = (
                "Operation execution failed"
            )

        finalization = db.execute(
            update(Operation)
            .where(
                Operation.id == operation_id,
                Operation.status == "running",
                Operation.attempt_count == attempt,
                Operation.lease_expires_at > now,
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        )

        db.commit()

        if finalization.rowcount == 1:
            logger.info(
                "Operation %s finished as %s",
                operation_id,
                outcome,
            )
        else:
            logger.warning(
                "Stale or expired attempt ignored: %s",
                operation_id,
            )

    finally:
        stop_event.set()

        if heartbeat is not None and heartbeat.is_alive():
            heartbeat.join(timeout=5)

        generator.close()


def handle_message(channel, method, properties, body):
    """Handle a RabbitMQ delivery safely."""

    try:
        message = json.loads(body)
        operation_id = str(UUID(message["operation_id"]))

    except (ValueError, KeyError, TypeError):
        logger.warning("Invalid operation message discarded")
        channel.basic_ack(
            delivery_tag=method.delivery_tag
        )
        return

    try:
        process_operation(operation_id)

    except Exception:
        logger.exception(
            "Unexpected operation processing error"
        )

        channel.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=True,
        )
        return

    channel.basic_ack(
        delivery_tag=method.delivery_tag
    )


def main():
    connection = open_connection()

    try:
        channel = connection.channel()

        declare_queue(channel)
        channel.basic_qos(prefetch_count=1)

        channel.basic_consume(
            queue=settings.operation_queue,
            on_message_callback=handle_message,
            auto_ack=False,
        )

        logger.info("Heartbeat-enabled worker started")
        channel.start_consuming()

    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()
