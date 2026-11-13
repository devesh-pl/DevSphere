"""DevSphere Service Catalog integration smoke test."""

from uuid import uuid4

from test_auth_flow import request as auth_request


def catalog_request(method, path, payload=None, token=None):
    import json
    import urllib.error
    import urllib.request

    headers = {"Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = json.dumps(payload).encode() if payload is not None else None

    req = urllib.request.Request(
        "http://localhost:8002" + path,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 204:
                return response.status, None
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def main():
    suffix = uuid4().hex[:12]
    email = f"catalog-{suffix}@example.com"
    password = "DevSphereSecure123!"

    status, user = auth_request(
        "POST",
        "/auth/register",
        {
            "email": email,
            "full_name": "Catalog Developer",
            "password": password,
        },
    )
    assert status == 201, (status, user)
    print("PASS: Developer registered")

    status, login = auth_request(
        "POST",
        "/auth/login",
        {"email": email, "password": password},
    )
    assert status == 200, (status, login)
    token = login["access_token"]
    print("PASS: Developer logged in")

    status, _ = catalog_request("GET", "/catalog/services")
    assert status == 401
    print("PASS: Unauthenticated request rejected")

    status, service = catalog_request(
        "POST",
        "/catalog/services",
        {
            "name": f"demo-api-{suffix}",
            "description": "DevSphere test application",
            "repository_url": "https://github.com/example/demo-api",
            "language": "Python",
            "framework": "FastAPI",
        },
        token,
    )
    assert status == 201, (status, service)
    assert service["owner_id"] == user["id"]
    print("PASS: Application registered")

    service_id = service["id"]

    status, services = catalog_request(
        "GET", "/catalog/services", token=token
    )
    assert status == 200
    assert any(item["id"] == service_id for item in services)
    print("PASS: Application appears in catalog")

    status, found = catalog_request(
        "GET", f"/catalog/services/{service_id}", token=token
    )
    assert status == 200
    assert found["id"] == service_id
    print("PASS: Application retrieved")

    status, _ = catalog_request(
        "DELETE", f"/catalog/services/{service_id}", token=token
    )
    assert status == 204
    print("PASS: Owner deleted application")

    status, _ = catalog_request(
        "GET", f"/catalog/services/{service_id}", token=token
    )
    assert status == 404
    print("PASS: Deleted application no longer exists")

    print("\nALL CATALOG INTEGRATION CHECKS PASSED")


if __name__ == "__main__":
    main()
