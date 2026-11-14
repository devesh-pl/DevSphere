"""End-to-end Build Service integration test."""

import json
import time
import urllib.error
import urllib.request

from uuid import uuid4


AUTH = "http://127.0.0.1:8001"
ORCH = "http://127.0.0.1:8004"
BUILD = "http://127.0.0.1:8006"


def api(method, url, data=None, token=None):
    headers = {"Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data is not None else None,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.load(response)

    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def wait_for(url, token, timeout=240):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        status, result = api("GET", url, token=token)
        assert status == 200, (status, result)

        if result["status"] in ("completed", "failed"):
            return result

        time.sleep(3)

    raise TimeoutError(f"Timed out waiting for {url}")


def main():
    suffix = uuid4().hex[:8]
    slug = f"build-api-{suffix}"

    credentials = {
        "email": f"build-{suffix}@example.com",
        "password": "DevSphereSecure123!",
    }

    status, _ = api(
        "POST",
        AUTH + "/auth/register",
        {**credentials, "full_name": "Build Tester"},
    )
    assert status == 201
    print("PASS: Developer registered")

    status, login = api(
        "POST", AUTH + "/auth/login", credentials
    )
    assert status == 200

    token = login["access_token"]
    print("PASS: Developer authenticated")

    status, operation = api(
        "POST",
        ORCH + "/operations",
        {
            "operation_type": "provision_project",
            "project_slug": slug,
            "template_id": "fastapi-basic",
            "repository_url": "https://github.com/example/build-demo",
        },
        token,
    )
    assert status == 202

    operation_id = operation["id"]
    print("PASS: Provisioning operation submitted")

    operation = wait_for(
        ORCH + f"/operations/{operation_id}",
        token,
    )
    assert operation["status"] == "completed", operation

    print("PASS: Project provisioned")

    status, job = api(
        "POST",
        BUILD + "/builds",
        {"operation_id": operation_id},
        token,
    )
    assert status == 202, (status, job)

    job_id = job["id"]
    print("PASS: Build submitted:", job_id)

    status, duplicate = api(
        "POST",
        BUILD + "/builds",
        {"operation_id": operation_id},
        token,
    )
    assert status == 202
    assert duplicate["id"] == job_id

    print("PASS: Duplicate build request reused")

    job = wait_for(
        BUILD + f"/builds/{job_id}",
        token,
    )
    assert job["status"] == "completed", job
    assert job["deployment_id"]
    assert job["kubernetes_name"]

    print("PASS: Image built and deployed")
    print("Deployment ID:", job["deployment_id"])
    print("Kubernetes name:", job["kubernetes_name"])

    status, records = api(
        "GET", BUILD + "/builds", token=token
    )
    assert status == 200
    assert any(item["id"] == job_id for item in records)

    print("PASS: Build available in history")
    print("\nALL BUILD SERVICE CHECKS PASSED")


if __name__ == "__main__":
    main()
