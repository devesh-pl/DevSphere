"""Tests for the DevSphere Template Service."""

from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import app


def developer():
    return {
        "id": "test-developer",
        "role": "developer",
        "is_active": True,
    }


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = developer

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_ready(client):
    response = client.get("/ready")
    assert response.status_code == 200


def test_list_templates(client):
    response = client.get("/templates")
    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_template_details(client):
    response = client.get("/templates/fastapi-basic")
    assert response.status_code == 200
    assert response.json()["framework"] == "FastAPI"


def test_unknown_template(client):
    response = client.get("/templates/unknown")
    assert response.status_code == 404


def test_generate_fastapi(client):
    response = client.post(
        "/templates/fastapi-basic/generate",
        json={"project_slug": "my-fastapi-app"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"

    with ZipFile(BytesIO(response.content)) as archive:
        assert archive.testzip() is None
        assert "my-fastapi-app/main.py" in archive.namelist()
        assert "my-fastapi-app/Dockerfile" in archive.namelist()


def test_generate_express(client):
    response = client.post(
        "/templates/express-basic/generate",
        json={"project_slug": "my-node-app"},
    )

    assert response.status_code == 200

    with ZipFile(BytesIO(response.content)) as archive:
        assert archive.testzip() is None
        assert "my-node-app/server.js" in archive.namelist()
        assert "my-node-app/package.json" in archive.namelist()


def test_invalid_project_slug(client):
    response = client.post(
        "/templates/fastapi-basic/generate",
        json={"project_slug": "../unsafe"},
    )
    assert response.status_code == 422


def test_viewer_cannot_generate(client):
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "test-viewer",
        "role": "viewer",
        "is_active": True,
    }

    response = client.post(
        "/templates/fastapi-basic/generate",
        json={"project_slug": "viewer-project"},
    )

    assert response.status_code == 403


def test_missing_authentication():
    with TestClient(app) as unauthenticated_client:
        response = unauthenticated_client.get("/templates")

    assert response.status_code == 401
