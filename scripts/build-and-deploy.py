"""Local DevSphere build-to-Kubernetes integration runner."""

import json
import subprocess
import time
import urllib.error
import urllib.request
import zipfile

from io import BytesIO
from pathlib import Path, PurePosixPath
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "build-runs"

AUTH = "http://localhost:8001"
ORCH = "http://localhost:8004"
DEPLOY = "http://localhost:8005"


def run(*command):
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True, cwd=ROOT)


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
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "")

            if "application/zip" in content_type:
                return response.status, body

            return response.status, json.loads(body)

    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read())
        except ValueError:
            detail = {"detail": "Non-JSON HTTP error"}

        raise RuntimeError(
            f"{method} {url} returned {error.code}: {detail}"
        ) from error


def wait_for_operation(operation_id, token, timeout=120):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        status, operation = api(
            "GET",
            f"{ORCH}/operations/{operation_id}",
            token=token,
        )

        if status != 200:
            raise RuntimeError(f"Operation lookup failed: {status}")

        if operation["status"] == "completed":
            return json.loads(operation["result"])

        if operation["status"] == "failed":
            raise RuntimeError(
                f"Provisioning failed: {operation.get('error_message')}"
            )

        time.sleep(2)

    raise TimeoutError("Provisioning did not complete")


def extract_project(archive_bytes, project_slug, destination):
    destination.mkdir(parents=True, exist_ok=False)

    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Invalid ZIP checksum")

        for member in archive.infolist():
            parts = PurePosixPath(member.filename).parts

            if (
                not parts
                or parts[0] != project_slug
                or any(part in ("..", "") for part in parts)
                or member.filename.startswith("/")
                or (member.external_attr >> 16) & 0o170000
                   == 0o120000
            ):
                raise RuntimeError("Unsafe archive member")

            target = destination.joinpath(*parts).resolve()

            if not target.is_relative_to(destination.resolve()):
                raise RuntimeError("Unsafe archive path")

            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)

            with archive.open(member) as source:
                with target.open("wb") as output:
                    while chunk := source.read(65536):
                        output.write(chunk)

    project = destination / project_slug

    for filename in ("main.py", "requirements.txt"):
        if not (project / filename).is_file():
            raise RuntimeError(f"Missing generated file: {filename}")

    return project


def build_image(project, image):
    dockerfile = project / "Dockerfile.devsphere"

    dockerfile.write_text(
        "FROM devsphere/orchestrator-service:0.1.0\n"
        "WORKDIR /app\n"
                "COPY main.py .\n"
        "USER 10001:10001\n"
        "EXPOSE 8000\n"
        'CMD ["uvicorn", "main:app", "--host", "0.0.0.0", '
        '"--port", "8000"]\n'
    )

    run(
        "docker", "build",
        "-t", image,
        "-f", str(dockerfile),
        str(project),
    )

    run(
        "kind", "load", "docker-image",
        image,
        "--name", "devsphere",
    )


def wait_for_deployment(deployment_id, token, timeout=180):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        _, result = api(
            "GET",
            f"{DEPLOY}/deployments/{deployment_id}",
            token=token,
        )

        print(
            "Kubernetes:",
            result["status"],
            f"{result.get('ready_replicas', 0)}/"
            f"{result.get('desired_replicas', 1)}",
            flush=True,
        )

        if result["status"] == "running":
            return result

        if result["status"] in ("failed", "missing", "deleted"):
            raise RuntimeError(f"Deployment did not succeed: {result}")

        time.sleep(3)

    raise TimeoutError("Kubernetes rollout timed out")


def main():
    suffix = uuid4().hex[:8]

    slug = f"built-api-{suffix}"
    email = f"builder-{suffix}@example.com"
    password = f"DevSphere-{uuid4().hex}!"
    image = f"devsphere-built/{slug}:{suffix}"

    print("\n===== DEVSPHERE BUILD AND DEPLOY =====\n")

    credentials = {
        "email": email,
        "password": password,
    }

    status, _ = api(
        "POST",
        AUTH + "/auth/register",
        {
            **credentials,
            "full_name": "Build Pipeline Test",
        },
    )
    assert status == 201
    print("PASS: Developer registered")

    status, login = api(
        "POST",
        AUTH + "/auth/login",
        credentials,
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
            "repository_url": (
                "https://github.com/example/devsphere-demo"
            ),
        },
        token,
    )

    assert status == 202
    operation_id = operation["id"]

    print("PASS: Provisioning submitted:", operation_id)

    result = wait_for_operation(operation_id, token)

    print("PASS: Project generated")
    print("Catalog ID:", result["catalog_service_id"])

    status, archive = api(
        "GET",
        ORCH + result["download_url"],
        token=token,
    )

    assert status == 200
    print("PASS: Source ZIP downloaded")

    project = extract_project(
        archive,
        slug,
        OUTPUT / operation_id,
    )

    print("PASS: Source files verified")

    build_image(project, image)
    print("PASS: Container image built and loaded into Kind")

    status, deployment = api(
        "POST",
        DEPLOY + "/deployments",
        {
            "name": slug,
            "image": image,
            "container_port": 8000,
            "replicas": 1,
        },
        token,
    )

    assert status == 201
    deployment_id = deployment["id"]

    print("PASS: Deployment requested:", deployment_id)

    try:
        ready = wait_for_deployment(deployment_id, token)
    except Exception:
        print("\nKubernetes diagnostics:")
        subprocess.run([
            "kubectl", "--context", "kind-devsphere",
            "-n", "devsphere-apps",
            "get", "pods", "-o", "wide",
        ])
        raise

    print("PASS: Application running on Kubernetes")

    summary = {
        "operation_id": operation_id,
        "catalog_service_id": result["catalog_service_id"],
        "deployment_id": deployment_id,
        "kubernetes_name": deployment["name"],
        "image": image,
        "namespace": ready["namespace"],
        "status": ready["status"],
    }

    report = OUTPUT / operation_id / "result.json"
    report.write_text(json.dumps(summary, indent=2))

    print("\n===== COMPLETE =====")
    print(json.dumps(summary, indent=2))
    print("\nPASS: End-to-end build and deployment")
    print("Report:", report)


if __name__ == "__main__":
    main()
