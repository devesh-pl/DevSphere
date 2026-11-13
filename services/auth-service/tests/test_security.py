"""Unit tests for authentication security utilities."""

from uuid import uuid4

import jwt
import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    monkeypatch.setenv(
        "AUTH_JWT_SECRET",
        "devsphere-testing-secret-that-is-not-for-production",
    )


def test_password_hashing():
    password = "SecurePassword123!"

    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)


def test_incorrect_password():
    hashed = hash_password("CorrectPassword123!")

    assert not verify_password("IncorrectPassword123!", hashed)


def test_create_and_decode_token():
    user_id = uuid4()

    token = create_access_token(user_id, "developer")
    payload = decode_access_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["role"] == "developer"
    assert payload["type"] == "access"


def test_invalid_token():
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token("invalid.jwt.token")


def test_missing_secret(monkeypatch):
    monkeypatch.delenv("AUTH_JWT_SECRET", raising=False)

    with pytest.raises(RuntimeError):
        create_access_token(uuid4(), "developer")
