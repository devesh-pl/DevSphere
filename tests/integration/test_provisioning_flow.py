"""End-to-end integration test for DevSphere project provisioning."""

import json
import time
import urllib.error
import urllib.request

from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile


AUTH_URL = "http://localhost:8001"
ORCHESTRATOR_URL = "http://localhost:8004"


def api_request(method, url, payload=None, token=None):
    headers = {"Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            content_type = response.headers.get("Content-Type", "")
            body = response.read()

            if "application/zip" in content_type:
                return response.status, body

            return response.status, json.loads(body)

    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")

        try:
            detail = json.loads(body)
        except ValueError:
            detail = {"raw_error": body}

        return error.code, detail


def main():
    suffix = uuid4().hex[:10]

    email = f"provisioning-{suffix}@example.com"
    password = "DevSphereSecure123!"
    project_slug = f"provisioned-api-{suffix}"

    print("\n===== DEVSPHERE PROVISIONING TEST =====\n")

    # STEP 1: Register developer.
    status, result = api_request(
        "POST",
        f"{AUTH_URL}/auth/register",
        {
            "email": email,
            "full_name": "Provisioning Developer",
            "password": password,
        },
    )

    assert status == 201, (status, result)

    print("PASS: Developer registered")

    # STEP 2: Login.
    status, result = api_request(
        "POST",
        f"{AUTH_URL}/auth/login",
        {
            "email": email,
            "password": password,
        },
    )

    assert status == 200, (status, result)

    token = result["access_token"]

    print("PASS: Developer logged in")

    # STEP 3: Submit provisioning operation.
    status, operation = api_request(
        "POST",
        f"{ORCHESTRATOR_URL}/operations",
        {
            "operation_type": "provision_project",
            "project_slug": project_slug,
            "template_id": "fastapi-basic",
            "repository_url": (
                "https://github.com/example/provisioned-api"
            ),
        },
        token,
    )

    assert status == 202, (status, operation)

    operation_id = operation["id"]

    print("PASS: Provisioning operation submitted")
    print("Operation ID:", operation_id)

    # STEP 4: Poll for completion.
    for attempt in range(60):
        status, operation = api_request(
            "GET",
            f"{ORCHESTRATOR_URL}/operations/{operation_id}",
            token=token,
        )

        assert status == 200, (status, operation)

        if operation["status"] in ("completed", "failed"):
            break

        time.sleep(0.5)

    else:
        raise AssertionError(
            "Provisioning operation did not complete within 30 seconds"
        )

    assert operation["status"] == "completed", operation

    print("PASS: RabbitMQ worker completed provisioning")

    # STEP 5: Validate result.
    result = json.loads(operation["result"])

    assert result["project_slug"] == project_slug
    assert result["template_id"] == "fastapi-basic"
    assert result["catalog_service_id"]

    print("PASS: Application registered in Service Catalog")
    print("Catalog Service ID:", result["catalog_service_id"])

    # STEP 6: Download generated project.
    status, archive_bytes = api_request(
        "GET",
        f"{ORCHESTRATOR_URL}{result['download_url']}",
        token=token,
    )

    assert status == 200, (status, archive_bytes)

    print("PASS: Generated application downloaded")

    # STEP 7: Verify generated ZIP.
    with ZipFile(BytesIO(archive_bytes)) as archive:
        assert archive.testzip() is None

        files = archive.namelist()

        assert f"{project_slug}/main.py" in files
        assert f"{project_slug}/Dockerfile" in files

    print("PASS: ZIP archive integrity verified")

    # STEP 8: Verify operation appears in history.
    status, history = api_request(
        "GET",
        f"{ORCHESTRATOR_URL}/operations",
        token=token,
    )

    assert status == 200, (status, history)
    assert any(item["id"] == operation_id for item in history)

    print("PASS: Provisioning operation appears in history")

    print("\nALL PROVISIONING INTEGRATION CHECKS PASSED\n")


if __name__ == "__main__":
    main()
