import json
import logging

from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):

    def format(self, record):

        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        optional_fields = [
            "service",
            "correlation_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
        ]

        for field in optional_fields:

            value = getattr(record, field, None)

            if value is not None:
                payload[field] = value

        if record.exc_info:

            payload["exception"] = self.formatException(
                record.exc_info
            )

        return json.dumps(payload, default=str)


def configure_logging(log_level: str):

    handler = logging.StreamHandler()

    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()

    root_logger.handlers.clear()

    root_logger.addHandler(handler)

    root_logger.setLevel(log_level.upper())

    access_logger = logging.getLogger("uvicorn.access")

    access_logger.handlers.clear()

    access_logger.propagate = True