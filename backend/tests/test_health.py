"""The health endpoint is what the container HEALTHCHECK and Coolify probe."""

from fastapi.testclient import TestClient

from lupus_ex_machina.app import create_app


def test_health_endpoint_reports_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
