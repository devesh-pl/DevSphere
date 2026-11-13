"""RabbitMQ worker for DevSphere operations."""

import json
import logging
from uuid import UUID

from sqlalchemy import update

from app.core.broker import declare_queue, open_connection
from app.core.config import settings
from app.core.provisioning import provision_project
from app.database.session import get_db
from app.models.operation import Operation


logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("devsphere.orchestrator.worker")


def process_operation(operation_id: str):
    generator = get_db()
    db = next(generator)

    try:
        claim = db.execute(
            update(Operation)
            .where(
                Operation.id == operation_id,
                Operation.status.in_(["pending", "queued"]),
            )
            .values(status="running", error_message=None)
        )
        db.commit()

        if claim.rowcount != 1:
            logger.info("Operation not claimable: %s", operation_id)
            return

        operation = db.get(Operation, operation_id)

        try:
            if operation.operation_type == "ping":
                result = {
                    "message": "pong",
                    "worker": "orchestrator-worker",
                }

            elif operation.operation_type == "provision_project":
                result = provision_project(
                    operation.id,
                    operation.owner_id,
                    operation.request_payload,
                )

            else:
                raise ValueError("Unsupported operation type")

            operation.result = json.dumps(result)
            operation.status = "completed"
            operation.error_message = None
            db.commit()

            logger.info("Completed operation: %s", operation_id)

        except Exception:
            logger.exception("Operation failed: %s", operation_id)
            db.rollback()

            operation = db.get(Operation, operation_id)
            operation.status = "failed"
            operation.error_message = "Operation execution failed"
            db.commit()

    finally:
        generator.close()


def handle_message(channel, method, properties, body):
    try:
        message = json.loads(body)
        operation_id = str(UUID(message["operation_id"]))
    except (ValueError, KeyError, TypeError):
        logger.exception("Invalid operation message")
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return

    try:
        process_operation(operation_id)
    except Exception:
        logger.exception("Unexpected processing error")
        channel.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=True,
        )
        return

    channel.basic_ack(delivery_tag=method.delivery_tag)


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

        logger.info("Orchestrator worker started")
        channel.start_consuming()

    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()
