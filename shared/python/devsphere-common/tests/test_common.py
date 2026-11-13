from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from devsphere_common.correlation import resolve_correlation_id
from devsphere_common.middleware import (
    install_correlation_id_middleware,
)


def test_valid_correlation_id_is_preserved():

    value = "devsphere-test-123"

    assert resolve_correlation_id(value) == value


def test_missing_correlation_id_generates_uuid():

    result = resolve_correlation_id(None)

    UUID(result)


def test_invalid_correlation_id_generates_uuid():

    result = resolve_correlation_id(
        "invalid id with spaces!"
    )

    UUID(result)


def test_middleware_preserves_correlation_id():

    app = FastAPI()

    install_correlation_id_middleware(
        app,
        "test-service",
    )

    @app.get("/test")
    def test_endpoint():
        return {"status": "ok"}

    client = TestClient(app)

    response = client.get(
        "/test",
        headers={
            "X-Correlation-ID": "test-123"
        },
    )

    assert response.status_code == 200

    assert (
        response.headers["X-Correlation-ID"]
        == "test-123"
    )