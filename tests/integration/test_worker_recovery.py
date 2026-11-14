"""Integration test for expired worker lease recovery."""

import json
import subprocess
import time
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


def compose(*args):
    return subprocess.check_output(
        COMPOSE + list(args),
        cwd=ROOT,
        text=True,
    )


def sql(query):
    return compose(
        "exec", "-T", "postgres",
        "psql",
        "-U", "orchestrator_service",
        "-d", "orchestrator_db",
        "-At", "-c", query,
    ).strip()


def api(method, url, data=None, token=None):
    headers = {"Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = json.dumps(data).encode() if data is not None else None

    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        return response.status, json.load(response)


def wait_until(predicate, timeout=45):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(1)

    return False


def main():
    print("\n===== DEVSPHERE WORKER RECOVERY TEST =====\n")

    suffix = uuid4().hex[:10]

    credentials = {
        "email": f"lease-{suffix}@example.com",
        "password": "DevSphereSecure123!",
    }

    status, _ = api(
        "POST",
        "http://localhost:8001/auth/register",
        {**credentials, "full_name": "Worker Recovery Tester"},
    )
    assert status == 201

    status, login = api(
        "POST",
        "http://localhost:8001/auth/login",
        credentials,
    )
    assert status == 200

    token = login["access_token"]
    print("PASS: Test developer authenticated")

    worker_stopped = False

    try:
        compose("stop", "orchestrator-worker")
        worker_stopped = True
        print("PASS: Worker stopped")

        status, operation = api(
            "POST",
            "http://localhost:8004/operations",
            {"operation_type": "ping"},
            token,
        )

        assert status == 202, (status, operation)
        operation_id = str(
            __import__("uuid").UUID(operation["id"])
        )

        print("PASS: Operation submitted:", operation_id)

        assert wait_until(
            lambda: sql(
                "SELECT status FROM operation_outbox "
                f"WHERE operation_id = '{operation_id}'"
            ) == "published"
        ), "Outbox event was not published"

        print("PASS: Outbox published operation")

        # Simulate an operation abandoned during its first attempt.
        # The worker is stopped, so no real execution is interrupted.
        sql(
            "UPDATE operations SET "
            "status = 'running', "
            "attempt_count = 1, "
            "last_heartbeat_at = NOW() - INTERVAL '120 seconds', "
            "lease_expires_at = NOW() - INTERVAL '60 seconds' "
            f"WHERE id = '{operation_id}';"
        )

        print("PASS: Expired worker lease simulated")

        assert wait_until(
            lambda: sql(
                "SELECT status FROM operations "
                f"WHERE id = '{operation_id}'"
            ) == "queued"
        ), "Recovery controller did not requeue operation"

        print("PASS: Recovery controller requeued operation")

    finally:
        if worker_stopped:
            compose(
                "up", "-d", "--no-build",
                "orchestrator-worker",
            )
            print("PASS: Worker restarted")

    assert wait_until(
        lambda: sql(
            "SELECT status FROM operations "
            f"WHERE id = '{operation_id}'"
        ) == "completed",
        timeout=60,
    ), "Recovered operation did not complete"

    attempts = int(sql(
        "SELECT attempt_count FROM operations "
        f"WHERE id = '{operation_id}'"
    ))

    assert attempts == 2, attempts

    print("PASS: Recovered operation completed")
    print("PASS: Attempt count increased from 1 to 2")

    print("\nALL WORKER RECOVERY CHECKS PASSED\n")


if __name__ == "__main__":
    main()
