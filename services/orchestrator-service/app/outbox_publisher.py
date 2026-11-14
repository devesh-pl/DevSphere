"""Reliable PostgreSQL outbox publisher for DevSphere."""

import logging
import signal
import time

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.core.broker import publish_operation
from app.core.config import settings
from app.database.session import get_db
from app.models.operation import Operation
from app.models.outbox import OperationOutbox


logging.basicConfig(level=settings.log_level)

logger = logging.getLogger(
    "devsphere.orchestrator.outbox"
)

POLL_INTERVAL = 2
MAX_BACKOFF_SECONDS = 60

running = True


def stop_handler(signum, frame):
    global running
    running = False


def publish_next_event():
    """Publish one event with PostgreSQL row locking."""

    generator = get_db()
    db = next(generator)

    try:
        now = datetime.now(timezone.utc)

        # SKIP LOCKED allows multiple publisher instances
        # to operate without claiming the same row.
        statement = (
            select(OperationOutbox)
            .where(
                OperationOutbox.status == "pending",
                OperationOutbox.next_attempt_at <= now,
            )
            .order_by(OperationOutbox.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )

        event = db.scalar(statement)

        if event is None:
            db.rollback()
            return False

        try:
            # Reuse the existing durable RabbitMQ publisher.
            # It enables publisher confirmations.
            publish_operation(event.operation_id)

            event.status = "published"
            event.published_at = datetime.now(timezone.utc)
            event.attempts += 1

            # Never overwrite operations already claimed
            # or completed by the worker.
            db.execute(
                update(Operation)
                .where(
                    Operation.id == event.operation_id,
                    Operation.status == "pending",
                )
                .values(status="queued")
            )

            db.commit()

            logger.info(
                "Published operation %s",
                event.operation_id,
            )

        except Exception:
            logger.exception(
                "Outbox publication failed for %s",
                event.operation_id,
            )

            db.rollback()

            # The unsuccessful publish is retried later.
            # The broker may have accepted a message even if
            # its confirmation was lost; consumer idempotency
            # is therefore still required.
            event = db.get(
                OperationOutbox,
                event.id,
                with_for_update=True,
            )

            if event.status == "pending":
                event.attempts += 1

                delay = min(
                    2 ** min(event.attempts, 6),
                    MAX_BACKOFF_SECONDS,
                )

                event.next_attempt_at = (
                    datetime.now(timezone.utc)
                    + timedelta(seconds=delay)
                )

            db.commit()

        return True

    except Exception:
        db.rollback()
        logger.exception("Outbox database error")
        raise

    finally:
        generator.close()


def main():
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)

    logger.info("DevSphere Outbox Publisher started")

    while running:
        try:
            found = publish_next_event()

            if not found:
                time.sleep(POLL_INTERVAL)

        except Exception:
            logger.exception("Publisher cycle failed")
            time.sleep(5)

    logger.info("DevSphere Outbox Publisher stopped")


if __name__ == "__main__":
    main()
