import re

from uuid import uuid4


CORRELATION_ID_HEADER = "X-Correlation-ID"

CORRELATION_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9._:-]{1,128}$"
)


def resolve_correlation_id(value: str | None) -> str:

    if (
        isinstance(value, str)
        and CORRELATION_ID_PATTERN.fullmatch(value)
    ):
        return value

    return str(uuid4())