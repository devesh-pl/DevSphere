"""DevSphere worker with heartbeats, leases and bounded retries."""

import json
import logging
import threading

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update

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
from app.models.outbox import OperationOutbox


logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("devsphere.orchestrator.worker")


def utc_now():
    return datetime.now(timezone.utc)


def new_session():
    generator = get_db()
    return generator, next(generator)


def heartbeat_loop(operation_id, attempt, stop_event):
    """Extend the lease only while this attempt still owns it."""

    while not stop_event.wait(WORKER_HEARTBEAT_SECONDS):
        generator, db = new_session()

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
                    last_heartbeat_at=now,
                    lease_expires_at=now + timedelta(
                        seconds=OPERATION_LEASE_SECONDS
                    ),
                )
                .execution_options(synchronize_session=False)
            )

            db.commit()

            if result.rowcount != 1:
                logger.warning(
                    "Heartbeat ownership lost: %s", operation_id
                )
                return

        except Exception:
            db.rollback()
            logger.exception(
                "Heartbeat database error: %s", operation_id
            )

        finally:
            generator.close()


def process_operation(operation_id):
    """Claim an operation and safely finalize its result."""

    generator, db = new_session()
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
                last_heartbeat_at=now,
                lease_expires_at=now + timedelta(
                    seconds=OPERATION_LEASE_SECONDS
                ),
                error_message=None,
            )
            .execution_options(synchronize_session=False)
        )

        db.commit()

        if claim.rowcount != 1:
            logger.info(
                "Operation not claimable: %s", operation_id
            )
            return

        operation = db.get(Operation, operation_id)

        attempt = operation.attempt_count
        operation_type = operation.operation_type
        owner_id = operation.owner_id
        request_payload = operation.request_payload

        logger.info(
            "Claimed %s attempt %s", operation_id, attempt
        )

        heartbeat = threading.Thread(
            target=heartbeat_loop,
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
                "Operation execution error: %s", operation_id
            )
            outcome = "failed"

        finally:
            stop_event.set()
            heartbeat.join(timeout=5)

        # Lock outbox first, consistent with recovery controller.
        event = db.scalar(
            select(OperationOutbox)
            .where(
                OperationOutbox.operation_id == operation_id
            )
            .with_for_update()
        )

        if event is None:
            db.rollback()
            raise RuntimeError("Outbox event missing")

        now = utc_now()

        if outcome == "completed":
            values = {
                "status": "completed",
                "result": json.dumps(result_data),
                "error_message": None,
                "lease_expires_at": None,
            }

        elif attempt < MAX_OPERATION_ATTEMPTS:
            delay = min(2 ** attempt, 30)

            values = {
                "status": "queued",
                "error_message": "Retry scheduled",
                "lease_expires_at": None,
            }

        else:
            values = {
                "status": "failed",
                "error_message": "Maximum attempts exceeded",
                "lease_expires_at": None,
            }

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

        if finalization.rowcount != 1:
            db.rollback()
            logger.warning(
                "Stale attempt discarded: %s", operation_id
            )
            return

        if outcome == "failed" and attempt < MAX_OPERATION_ATTEMPTS:
            event.status = "pending"
            event.published_at = None
            event.next_attempt_at = now + timedelta(
                seconds=delay
            )

            logger.warning(
                "Retry scheduled: %s, attempt=%s, delay=%ss",
                operation_id,
                attempt,
                delay,
            )

        db.commit()

        logger.info(
            "Operation %s status=%s",
            operation_id,
            values["status"],
        )

    except Exception:
        db.rollback()
        logger.exception(
            "Unexpected worker failure: %s", operation_id
        )
        raise

    finally:
        stop_event.set()

        if heartbeat is not None and heartbeat.is_alive():
            heartbeat.join(timeout=5)

        generator.close()


def handle_message(channel, method, properties, body):
    """Consume one operation message."""

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
        logger.exception("Message processing failed")
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

        logger.info("Reliable Orchestrator Worker started")
        channel.start_consuming()

    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()
