"""DevSphere Kubernetes Deployment Service integration test."""

import json
import time
import urllib.error
import urllib.request

from uuid import uuid4


AUTH = "http://localhost:8001"
DEPLOY = "http://localhost:8005"


def api(method, url, payload=None, token=None):
    headers = {"Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = json.dumps(payload).encode() if payload is not None else None

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.load(response)

    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def developer():
    suffix = uuid4().hex[:10]
    creds = {
        "email": f"k8s-{suffix}@example.com",
        "password": "DevSphereSecure123!",
    }

    status, response = api(
        "POST",
        AUTH + "/auth/register",
        {**creds, "full_name": "Kubernetes Developer"},
    )
    assert status == 201, (status, response)

    status, response = api("POST", AUTH + "/auth/login", creds)
    assert status == 200, (status, response)

    return response["access_token"]


def main():
    print("\n===== DEVSPHERE KUBERNETES TEST =====\n")

    owner = developer()
    other = developer()

    print("PASS: Two developers authenticated")

    status, result = api(
        "POST",
        DEPLOY + "/deployments",
        {
            "name": "kubernetes-demo",
            "image": "nginxinc/nginx-unprivileged:stable-alpine",
            "container_port": 8080,
            "replicas": 1,
        },
        owner,
    )

    assert status == 201, (status, result)

    deployment_id = result["id"]
    print("PASS: Kubernetes Deployment created")
    print("Deployment ID:", deployment_id)
    print("Kubernetes name:", result["name"])

    try:
        for _ in range(90):
            status, result = api(
                "GET",
                DEPLOY + f"/deployments/{deployment_id}",
                token=owner,
            )
            assert status == 200, (status, result)

            if result["status"] == "running":
                break

            time.sleep(2)
        else:
            raise AssertionError("Kubernetes workload not ready")

        print("PASS: Kubernetes pod running")
        print("PASS: Ready replicas:", result["ready_replicas"])

        status, records = api(
            "GET",
            DEPLOY + "/deployments",
            token=owner,
        )
        assert status == 200
        assert any(x["id"] == deployment_id for x in records)

        print("PASS: Deployment stored in PostgreSQL")

        status, _ = api(
            "GET",
            DEPLOY + f"/deployments/{deployment_id}",
            token=other,
        )
        assert status == 404

        print("PASS: Cross-developer access denied")

        status, _ = api(
            "DELETE",
            DEPLOY + f"/deployments/{deployment_id}",
            token=other,
        )
        assert status == 404

        print("PASS: Cross-developer deletion denied")

        status, _ = api("GET", DEPLOY + "/deployments")
        assert status in (401, 403)

        print("PASS: Unauthenticated access denied")

    finally:
        status, result = api(
            "DELETE",
            DEPLOY + f"/deployments/{deployment_id}",
            token=owner,
        )
        assert status == 200, (status, result)

    print("PASS: Kubernetes deployment deleted")
    print("\nALL KUBERNETES DEPLOYMENT CHECKS PASSED\n")


if __name__ == "__main__":
    main()
