"""Authentication for trusted DevSphere service-to-service requests."""

import os
import secrets

from fastapi import Header, HTTPException


def require_internal_service(
    x_devsphere_internal_token: str | None = Header(default=None),
):
    expected = os.environ.get("DEVSPHERE_INTERNAL_TOKEN", "")

    if len(expected) < 32:
        raise HTTPException(
            status_code=503,
            detail="Internal authentication is not configured",
        )

    if not x_devsphere_internal_token or not secrets.compare_digest(
        x_devsphere_internal_token,
        expected,
    ):
        raise HTTPException(
            status_code=403,
            detail="Internal service authentication failed",
        )

    return True
