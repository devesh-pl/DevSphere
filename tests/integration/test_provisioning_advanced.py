"""Test Express provisioning and cross-user access isolation."""

import json
import time
import urllib.error
import urllib.request

from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile


AUTH = "http://localhost:8001"
ORCH = "http://localhost:8004"


def api(method, url, data=None, token=None):
    headers = {"Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = json.dumps(data).encode() if data is not None else None

    request = urllib.request.Request(
        url, data=body, headers=headers, method=method
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            content = response.read()
            if "application/zip" in response.headers.get(
                "Content-Type", ""
            ):
                return response.status, content

            return response.status, json.loads(content)

    except urllib.error.HTTPError as error:
        content = error.read()
        try:
            return error.code, json.loads(content)
        except ValueError:
            return error.code, content.decode(errors="replace")


def create_developer():
    suffix = uuid4().hex[:10]
    credentials = {
        "email": f"advanced-{suffix}@example.com",
        "password": "DevSphereSecure123!",
    }

    status, response = api(
        "POST",
        AUTH + "/auth/register",
        {
            **credentials,
            "full_name": "Advanced Test Developer",
        },
    )

    assert status == 201, (status, response)

    status, response = api(
        "POST",
        AUTH + "/auth/login",
        credentials,
    )

    assert status == 200, (status, response)
    return response["access_token"]


def main():
    print("\n===== DEVSPHERE ADVANCED TEST =====\n")

    developer_a = create_developer()
    developer_b = create_developer()

    print("PASS: Two independent developers created")

    slug = f"express-demo-{uuid4().hex[:8]}"

    status, operation = api(
        "POST",
        ORCH + "/operations",
        {
            "operation_type": "provision_project",
            "project_slug": slug,
            "template_id": "express-basic",
            "repository_url": "https://github.com/example/express-demo",
        },
        developer_a,
    )

    assert status == 202, (status, operation)
    operation_id = operation["id"]

    print("PASS: Express provisioning request accepted")
    print("Operation ID:", operation_id)

    for _ in range(60):
        status, operation = api(
            "GET",
            f"{ORCH}/operations/{operation_id}",
            token=developer_a,
        )

        assert status == 200, (status, operation)

        if operation["status"] in ("completed", "failed"):
            break

        time.sleep(0.5)
    else:
        raise AssertionError("Operation timed out")

    assert operation["status"] == "completed", operation

    result = json.loads(operation["result"])

    assert result["template_id"] == "express-basic"
    assert result["catalog_service_id"]

    print("PASS: Express project generated and registered")

    download_url = ORCH + result["download_url"]

    status, archive = api(
        "GET", download_url, token=developer_a
    )

    assert status == 200, (status, archive)

    with ZipFile(BytesIO(archive)) as zip_file:
        assert zip_file.testzip() is None
        assert f"{slug}/server.js" in zip_file.namelist()

    print("PASS: Express ZIP downloaded and validated")

    status, response = api(
        "GET",
        f"{ORCH}/operations/{operation_id}",
        token=developer_b,
    )

    assert status == 404, (status, response)

    print("PASS: Another developer cannot view operation")

    status, response = api(
        "GET",
        download_url,
        token=developer_b,
    )

    assert status == 404, (status, response)

    print("PASS: Another developer cannot download ZIP")

    status, response = api(
        "GET",
        download_url,
    )

    assert status in (401, 403), (status, response)

    print("PASS: Unauthenticated ZIP download rejected")

    print("\nALL ADVANCED INTEGRATION CHECKS PASSED\n")


if __name__ == "__main__":
    main()
