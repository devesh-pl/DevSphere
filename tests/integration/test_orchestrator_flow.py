"""End-to-end integration test for DevSphere Orchestrator."""

import json
import time
import urllib.error
import urllib.request
from uuid import uuid4


AUTH_URL = "http://localhost:8001"
ORCHESTRATOR_URL = "http://localhost:8004"


def request(method, url, payload=None, token=None):
    headers = {"Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = json.dumps(payload).encode() if payload is not None else None

    req = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def main():
    suffix = uuid4().hex[:12]
    email = f"orchestrator-{suffix}@example.com"
    password = "DevSphereSecure123!"

    print("\n===== DEVSPHERE ORCHESTRATOR TEST =====\n")

    # 1. Register developer
    status, user = request(
        "POST",
        AUTH_URL + "/auth/register",
        {
            "email": email,
            "full_name": "Orchestrator Test Developer",
            "password": password,
        },
    )

    assert status == 201, (status, user)
    print("PASS: Developer registered")

    # 2. Login
    status, login = request(
        "POST",
        AUTH_URL + "/auth/login",
        {
            "email": email,
            "password": password,
        },
    )

    assert status == 200, (status, login)
    token = login["access_token"]
    print("PASS: Developer logged in")

    # 3. Reject unauthenticated operations
    status, _ = request(
        "POST",
        ORCHESTRATOR_URL + "/operations",
        {"operation_type": "ping"},
    )

    assert status == 401
    print("PASS: Unauthenticated operation rejected")

    # 4. Queue an operation
    status, operation = request(
        "POST",
        ORCHESTRATOR_URL + "/operations",
        {"operation_type": "ping"},
        token,
    )

    assert status == 202, (status, operation)
    assert operation["owner_id"] == user["id"]

    operation_id = operation["id"]
    print("PASS: Operation queued:", operation_id)

    # 5. Wait for worker to complete it
    for _ in range(30):
        status, result = request(
            "GET",
            ORCHESTRATOR_URL + f"/operations/{operation_id}",
            token=token,
        )

        assert status == 200, (status, result)

        if result["status"] in ("completed", "failed"):
            break

        time.sleep(0.5)
    else:
        raise AssertionError("Operation did not complete")

    assert result["status"] == "completed", result

    payload = json.loads(result["result"])
    assert payload["message"] == "pong"

    print("PASS: RabbitMQ worker processed operation")
    print("PASS: PostgreSQL operation marked completed")

    # 6. Verify operation history
    status, operations = request(
        "GET",
        ORCHESTRATOR_URL + "/operations",
        token=token,
    )

    assert status == 200
    assert any(item["id"] == operation_id for item in operations)

    print("PASS: Operation available in history")
    print("\nALL ORCHESTRATOR INTEGRATION CHECKS PASSED")


if __name__ == "__main__":
    main()
