"""DevSphere Auth Service HTTP integration smoke test."""

import json
import urllib.error
import urllib.request
from uuid import uuid4

BASE_URL = "http://localhost:8001"


def request(method, path, payload=None, token=None):
    headers = {"Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = None

    if payload is not None:
        body = json.dumps(payload).encode()

    req = urllib.request.Request(
        BASE_URL + path,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def assert_status(actual, expected, name):
    assert actual == expected, (
        f"{name}: expected {expected}, got {actual}"
    )
    print(f"PASS: {name} ({actual})")


def main():
    email = f"devsphere-test-{uuid4().hex[:12]}@example.com"
    password = "DevSphereSecure123!"

    print("\n===== DEVSPHERE AUTH INTEGRATION TEST =====\n")

    status, user = request(
        "POST",
        "/auth/register",
        {
            "email": email,
            "full_name": "DevSphere Test Developer",
            "password": password,
        },
    )

    assert_status(status, 201, "Register developer")
    assert user["role"] == "developer"
    assert "password_hash" not in user

    status, _ = request(
        "POST",
        "/auth/register",
        {
            "email": email,
            "full_name": "Duplicate Developer",
            "password": password,
        },
    )

    assert_status(status, 409, "Reject duplicate email")

    status, _ = request(
        "POST",
        "/auth/login",
        {
            "email": email,
            "password": "IncorrectPassword123!",
        },
    )

    assert_status(status, 401, "Reject incorrect password")

    status, login = request(
        "POST",
        "/auth/login",
        {
            "email": email,
            "password": password,
        },
    )

    assert_status(status, 200, "Login developer")
    token = login["access_token"]
    assert login["token_type"] == "bearer"

    status, profile = request(
        "GET",
        "/auth/me",
        token=token,
    )

    assert_status(status, 200, "Read authenticated profile")
    assert profile["id"] == user["id"]
    assert profile["email"] == email

    status, _ = request("GET", "/auth/me")

    assert_status(status, 401, "Reject unauthenticated access")

    status, _ = request(
        "GET",
        "/auth/admin/check",
        token=token,
    )

    assert_status(status, 403, "Enforce admin-only access")

    print("\nALL AUTH INTEGRATION CHECKS PASSED")


if __name__ == "__main__":
    main()
