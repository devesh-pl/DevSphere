"""Verify outbox delivery after publisher interruption."""

import json
import subprocess
import time
import urllib.error
import urllib.request

from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]

COMPOSE = [
    "docker", "compose",
    "--env-file", ".env",
    "-f", "infrastructure/docker/docker-compose.yml",
    "-f", "infrastructure/docker/docker-compose.dev.yml",
]

AUTH = "http://localhost:8001"
ORCH = "http://localhost:8004"


def api(method, url, payload=None, token=None):
    headers = {"Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = (
        json.dumps(payload).encode()
        if payload is not None
        else None
    )

    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def compose(*args):
    subprocess.run(
        COMPOSE + list(args),
        cwd=ROOT,
        check=True,
    )


def outbox_status(operation_id):
    # UUID validation prevents arbitrary SQL content.
    operation_id = str(uuid4()) if operation_id is None else str(
        __import__("uuid").UUID(operation_id)
    )

    command = COMPOSE + [
        "exec", "-T", "postgres",
        "psql",
        "-U", "orchestrator_service",
        "-d", "orchestrator_db",
        "-At",
        "-c",
        (
            "SELECT status FROM operation_outbox "
            f"WHERE operation_id = '{operation_id}';"
        ),
    ]

    output = subprocess.check_output(
        command,
        cwd=ROOT,
        text=True,
    )

    return output.strip()


def main():
    print("\n===== DEVSPHERE OUTBOX RECOVERY TEST =====\n")

    source = (
        ROOT /
        "services/orchestrator-service/app/api/routes/operations.py"
    ).read_text()

    assert "db.add(outbox_event)" in source, (
        "Outbox implementation not found in operations.py"
    )

    suffix = uuid4().hex[:10]

    credentials = {
        "email": f"outbox-{suffix}@example.com",
        "password": "DevSphereSecure123!",
    }

    status, result = api(
        "POST",
        AUTH + "/auth/register",
        {
            **credentials,
            "full_name": "Outbox Recovery Tester",
        },
    )

    assert status == 201, (status, result)

    status, result = api(
        "POST",
        AUTH + "/auth/login",
        credentials,
    )

    assert status == 200, (status, result)

    token = result["access_token"]
    print("PASS: Test developer authenticated")

    publisher_stopped = False

    try:
        print("\nStopping Outbox Publisher...")
        compose("stop", "orchestrator-publisher")
        publisher_stopped = True

        print("PASS: Publisher stopped")

        status, operation = api(
            "POST",
            ORCH + "/operations",
            {"operation_type": "ping"},
            token,
        )

        assert status == 202, (status, operation)

        operation_id = operation["id"]

        print("PASS: Operation accepted while publisher offline")
        print("Operation ID:", operation_id)

        time.sleep(2)

        status, operation = api(
            "GET",
            ORCH + f"/operations/{operation_id}",
            token=token,
        )

        assert status == 200
        assert operation["status"] == "pending", operation

        print("PASS: Operation safely stored as pending")

        recorded_status = outbox_status(operation_id)
        assert recorded_status == "pending", recorded_status

        print("PASS: Durable pending outbox event exists")

    finally:
        if publisher_stopped:
            print("\nRestarting Outbox Publisher...")
            compose("up", "-d", "--no-build", "orchestrator-publisher")

    print("PASS: Publisher restarted")

    for _ in range(90):
        status, operation = api(
            "GET",
            ORCH + f"/operations/{operation_id}",
            token=token,
        )

        assert status == 200, (status, operation)

        if operation["status"] in ("completed", "failed"):
            break

        time.sleep(1)
    else:
        raise AssertionError("Operation did not recover within 90 seconds")

    assert operation["status"] == "completed", operation

    print("PASS: Worker completed recovered operation")

    recorded_status = outbox_status(operation_id)
    assert recorded_status == "published", recorded_status

    print("PASS: Outbox event marked published")

    print("\nALL OUTBOX RECOVERY CHECKS PASSED\n")


if __name__ == "__main__":
    main()
