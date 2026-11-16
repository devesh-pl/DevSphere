"""DevSphere deployment update and rollback integration test."""

import time
from uuid import uuid4

from test_build_service import (
    api, wait_for, AUTH, ORCH, BUILD
)

DEPLOY = "http://127.0.0.1:8005"


def wait_for_replicas(deployment_id, token, expected):
    deadline = time.monotonic() + 120

    while time.monotonic() < deadline:
        status, record = api(
            "GET",
            f"{DEPLOY}/deployments/{deployment_id}",
            token=token,
        )

        assert status == 200, (status, record)

        if (
            record["status"] == "running"
            and record["ready_replicas"] == expected
            and record["desired_replicas"] == expected
        ):
            return

        time.sleep(3)

    raise TimeoutError(
        f"Deployment did not reach {expected} ready replicas"
    )


def main():
    suffix = uuid4().hex[:8]

    credentials = {
        "email": f"rollout-{suffix}@example.com",
        "password": "DevSphereSecure123!",
    }

    status, response = api(
        "POST",
        AUTH + "/auth/register",
        {**credentials, "full_name": "Rollout Tester"},
    )
    assert status == 201, response

    status, login = api(
        "POST", AUTH + "/auth/login", credentials
    )
    assert status == 200, login

    token = login["access_token"]
    print("PASS: Developer authenticated")

    status, operation = api(
        "POST",
        ORCH + "/operations",
        {
            "operation_type": "provision_project",
            "project_slug": f"rollout-{suffix}",
            "template_id": "fastapi-basic",
            "repository_url": "https://github.com/example/rollout",
        },
        token,
    )
    assert status == 202, operation

    operation = wait_for(
        ORCH + f"/operations/{operation['id']}",
        token,
    )
    assert operation["status"] == "completed"

    status, job = api(
        "POST",
        BUILD + "/builds",
        {"operation_id": operation["id"]},
        token,
    )
    assert status == 202, job

    job = wait_for(
        BUILD + f"/builds/{job['id']}",
        token,
    )
    assert job["status"] == "completed", job

    deployment_id = job["deployment_id"]
    print("PASS: Application built and deployed")

    wait_for_replicas(deployment_id, token, 1)
    print("PASS: Initial replica count 1/1")

    url = f"{DEPLOY}/deployments/{deployment_id}"

    status, response = api(
        "PATCH",
        url,
        {"replicas": 2},
        token,
    )
    assert status == 200, (status, response)
    assert response["revision"] == 2

    wait_for_replicas(deployment_id, token, 2)
    print("PASS: Deployment scaled to 2/2")

    status, revisions = api(
        "GET",
        url + "/revisions",
        token=token,
    )
    assert status == 200
    assert [r["revision_number"] for r in revisions] == [2, 1]
    print("PASS: Initial and updated revisions persisted")

    status, response = api(
        "POST",
        url + "/rollback",
        {"revision": 1},
        token,
    )
    assert status == 200, (status, response)
    assert response["revision"] == 3
    assert response["restored_from"] == 1

    wait_for_replicas(deployment_id, token, 1)
    print("PASS: Deployment restored to 1/1")

    status, revisions = api(
        "GET",
        url + "/revisions",
        token=token,
    )
    assert status == 200
    assert [r["revision_number"] for r in revisions] == [3, 2, 1]
    assert revisions[0]["change_type"] == "rollback"

    print("PASS: Rollback recorded as revision 3")
    print("Deployment ID:", deployment_id)
    print("\nALL DEPLOYMENT ROLLBACK CHECKS PASSED")


if __name__ == "__main__":
    main()
