"""Authenticate requests through the DevSphere Auth Service."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    request = Request(
        f"{settings.auth_service_url.rstrip('/')}/auth/me",
        headers={
            "Authorization": f"Bearer {credentials.credentials}",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=5) as response:
            user = json.load(response)

    except HTTPError as error:
        if error.code in (401, 403):
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable",
        )

    except (URLError, TimeoutError, OSError, ValueError):
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable",
        )

    if not isinstance(user, dict):
        raise HTTPException(
            status_code=503,
            detail="Invalid authentication service response",
        )

    if not user.get("id") or not user.get("is_active"):
        raise HTTPException(
            status_code=401,
            detail="Inactive or invalid user",
        )

    return user
