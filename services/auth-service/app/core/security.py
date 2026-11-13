"""Password hashing and JWT authentication utilities."""

import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash


password_hasher = PasswordHash.recommended()

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "devsphere-auth"
JWT_AUDIENCE = "devsphere-api"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def hash_password(password: str) -> str:
    """Hash a password using Argon2."""
    return password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored hash."""
    return password_hasher.verify(plain_password, hashed_password)


def get_jwt_secret() -> str:
    """Read the signing secret securely from the environment."""
    secret = os.environ.get("AUTH_JWT_SECRET")

    if not secret or len(secret) < 32:
        raise RuntimeError(
            "AUTH_JWT_SECRET must be configured with at least 32 characters."
        )

    return secret


def create_access_token(user_id: UUID | str, role: str) -> str:
    """Generate a signed JWT access token."""
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }

    return jwt.encode(
        payload,
        get_jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    """Verify and decode a JWT access token."""
    payload = jwt.decode(
        token,
        get_jwt_secret(),
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
        options={"require": ["sub", "exp", "iat", "iss", "aud", "type"]},
    )

    if payload.get("type") != "access":
        raise InvalidTokenError("Invalid token type.")

    UUID(payload["sub"])

    return payload
