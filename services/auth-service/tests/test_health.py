from fastapi.testclient import TestClient

from app.main import app

from app.api.routes import health as health_routes


client = TestClient(app)


def test_health_endpoint():

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"

    assert data["service"] == "auth-service"


def test_readiness_without_database_requirement(monkeypatch):

    monkeypatch.setattr(
        health_routes.settings,
        "database_required",
        False,
    )

    response = client.get("/ready")

    assert response.status_code == 200

    assert response.json()["status"] == "ready"


def test_readiness_fails_when_database_unavailable(monkeypatch):

    monkeypatch.setattr(
        health_routes.settings,
        "database_required",
        True,
    )

    def database_failure():

        raise RuntimeError("Database unavailable")

    monkeypatch.setattr(
        health_routes,
        "check_database_connection",
        database_failure,
    )

    response = client.get("/ready")

    assert response.status_code == 503

    assert response.json()["reason"] == "database_unavailable"


def test_correlation_id_is_preserved():

    correlation_id = "devsphere-test-123"

    response = client.get(
        "/health",
        headers={
            "X-Correlation-ID": correlation_id
        },
    )

    assert response.status_code == 200

    assert response.headers["X-Correlation-ID"] == correlation_id


def test_invalid_correlation_id_is_replaced():

    response = client.get(
        "/health",
        headers={
            "X-Correlation-ID": "invalid id with spaces!"
        },
    )

    assert response.status_code == 200

    generated_id = response.headers["X-Correlation-ID"]

    assert generated_id != "invalid id with spaces!"

    assert len(generated_id) > 0