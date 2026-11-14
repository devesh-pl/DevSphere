"""Recover abandoned DevSphere operations using PostgreSQL leases."""

import logging
import signal
import time

from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.recovery_config import (
    MAX_OPERATION_ATTEMPTS,
    RECOVERY_SCAN_SECONDS,
)
from app.database.session import get_db
from app.models.operation import Operation
from app.models.outbox import OperationOutbox


logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("devsphere.orchestrator.recovery")

running = True


def utc_now():
    return datetime.now(timezone.utc)


def stop_handler(signum, frame):
    global running
    running = False


def find_expired_ids(limit=20):
    """Find candidate operations without acquiring persistent locks."""

    generator = get_db()
    db = next(generator)

    try:
        statement = (
            select(Operation.id)
            .where(
                Operation.status == "running",
                Operation.lease_expires_at.is_not(None),
                Operation.lease_expires_at <= utc_now(),
            )
            .order_by(Operation.lease_expires_at)
            .limit(limit)
        )

        return list(db.scalars(statement).all())

    finally:
        generator.close()


def recover_operation(operation_id):
    """Requeue one expired attempt, or mark it permanently failed."""

    generator = get_db()
    db = next(generator)

    try:
        # Lock outbox first, matching the publisher's lock order.
        event = db.scalar(
            select(OperationOutbox)
            .where(
                OperationOutbox.operation_id == operation_id
            )
            .with_for_update(skip_locked=True)
        )

        if event is None:
            db.rollback()
            logger.warning(
                "Outbox unavailable for recovery: %s",
                operation_id,
            )
            return False

        operation = db.scalar(
            select(Operation)
            .where(Operation.id == operation_id)
            .with_for_update(skip_locked=True)
        )

        if operation is None:
            db.rollback()
            return False

        now = utc_now()

        # Recheck while holding the database row locks.
        if (
            operation.status != "running"
            or operation.lease_expires_at is None
            or operation.lease_expires_at > now
        ):
            db.rollback()
            return False

        if operation.attempt_count >= MAX_OPERATION_ATTEMPTS:
            operation.status = "failed"
            operation.error_message = (
                "Maximum worker recovery attempts exceeded"
            )
            operation.lease_expires_at = None

            db.commit()

            logger.error(
                "Operation exhausted recovery attempts: %s",
                operation_id,
            )
            return True

        # Requeue without creating another outbox row.
        operation.status = "queued"
        operation.lease_expires_at = None
        operation.error_message = (
            "Previous worker attempt expired; retry queued"
        )

        event.status = "pending"
        event.next_attempt_at = now
        event.published_at = None

        db.commit()

        logger.warning(
            "Recovered operation %s, previous attempts=%s",
            operation_id,
            operation.attempt_count,
        )

        return True

    except Exception:
        db.rollback()
        logger.exception(
            "Failed recovering operation: %s",
            operation_id,
        )
        raise

    finally:
        generator.close()


def scan_expired_operations():
    candidates = find_expired_ids()

    for operation_id in candidates:
        recover_operation(operation_id)

    return len(candidates)


def main():
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)

    logger.info("DevSphere Recovery Controller started")

    while running:
        try:
            scan_expired_operations()

        except Exception:
            logger.exception("Recovery scan failed")

        time.sleep(RECOVERY_SCAN_SECONDS)

    logger.info("DevSphere Recovery Controller stopped")


if __name__ == "__main__":
    main()
