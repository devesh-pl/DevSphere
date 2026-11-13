"""Coordinate DevSphere project generation and Catalog registration."""

import json
import os
import tempfile
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path
from uuid import UUID
from zipfile import BadZipFile, ZipFile


TEMPLATE_URL = os.getenv(
    "TEMPLATE_SERVICE_URL", "http://template-service:8000"
).rstrip("/")

CATALOG_URL = os.getenv(
    "CATALOG_SERVICE_URL", "http://catalog-service:8000"
).rstrip("/")

ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "/app/artifacts"))
MAX_RESPONSE_BYTES = 3 * 1024 * 1024


class ProvisioningError(Exception):
    pass


def post_internal(url: str, payload: dict):
    token = os.getenv("DEVSPHERE_INTERNAL_TOKEN", "")

    if len(token) < 32:
        raise ProvisioningError("Internal credential missing")

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-DevSphere-Internal-Token": token,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                raise ProvisioningError("Response too large")
            return data, response.headers.get("Content-Type", "")

    except urllib.error.HTTPError as error:
        raise ProvisioningError(
            f"Internal service returned HTTP {error.code}"
        ) from error

    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ProvisioningError("Internal service unavailable") from error


def generate_archive(template_id: str, project_slug: str) -> bytes:
    if template_id not in ("fastapi-basic", "express-basic"):
        raise ProvisioningError("Unsupported template")

    archive_bytes, content_type = post_internal(
        f"{TEMPLATE_URL}/internal/templates/{template_id}/generate",
        {"project_slug": project_slug},
    )

    if "application/zip" not in content_type:
        raise ProvisioningError("Expected application/zip")

    try:
        with ZipFile(BytesIO(archive_bytes)) as archive:
            if archive.testzip() is not None:
                raise ProvisioningError("Invalid ZIP checksum")

            required = (
                f"{project_slug}/main.py"
                if template_id == "fastapi-basic"
                else f"{project_slug}/server.js"
            )

            if required not in archive.namelist():
                raise ProvisioningError("Generated entry point missing")

    except BadZipFile as error:
        raise ProvisioningError("Invalid ZIP archive") from error

    return archive_bytes


def save_archive(operation_id: str, content: bytes) -> Path:
    UUID(operation_id)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    destination = ARTIFACT_DIR / f"{operation_id}.zip"

    fd, temporary = tempfile.mkstemp(
        prefix=".devsphere-",
        suffix=".tmp",
        dir=ARTIFACT_DIR,
    )

    try:
        with os.fdopen(fd, "wb") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

    return destination


def register_catalog(
    operation_id: str,
    owner_id: str,
    project_slug: str,
    template_id: str,
    repository_url: str,
):
    definitions = {
        "fastapi-basic": ("Python", "FastAPI"),
        "express-basic": ("JavaScript", "Express"),
    }

    language, framework = definitions[template_id]

    body, content_type = post_internal(
        f"{CATALOG_URL}/internal/catalog/services",
        {
            "operation_id": operation_id,
            "owner_id": owner_id,
            "name": project_slug,
            "description": f"Generated using {template_id}",
            "repository_url": repository_url,
            "language": language,
            "framework": framework,
        },
    )

    if "application/json" not in content_type:
        raise ProvisioningError("Invalid Catalog response type")

    try:
        catalog = json.loads(body)
        UUID(catalog["id"])

        if catalog["owner_id"] != owner_id:
            raise ProvisioningError("Catalog owner mismatch")

        return catalog

    except (ValueError, KeyError, TypeError) as error:
        raise ProvisioningError("Invalid Catalog response") from error


def provision_project(
    operation_id: str,
    owner_id: str,
    request_payload: str,
):
    payload = json.loads(request_payload)

    archive = generate_archive(
        payload["template_id"],
        payload["project_slug"],
    )

    save_archive(operation_id, archive)

    catalog = register_catalog(
        operation_id,
        owner_id,
        payload["project_slug"],
        payload["template_id"],
        payload["repository_url"],
    )

    return {
        "project_slug": payload["project_slug"],
        "template_id": payload["template_id"],
        "catalog_service_id": catalog["id"],
        "artifact_filename": f"{operation_id}.zip",
        "download_url": f"/operations/{operation_id}/download",
    }
