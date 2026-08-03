"""The API process also serves the built front end, so there is a single origin."""

from pathlib import Path

from fastapi.testclient import TestClient

from lupus_ex_machina.app import create_app
from lupus_ex_machina.config import Settings


def build_frontend(directory: Path) -> Path:
    """Write the minimal output a real Vite build would produce."""
    directory.mkdir(parents=True)
    (directory / "index.html").write_text(
        "<!doctype html><title>Lupus Ex Machina</title>", encoding="utf-8"
    )
    (directory / "assets").mkdir()
    (directory / "assets" / "index.js").write_text("export default 0\n", encoding="utf-8")
    return directory


def test_root_serves_the_frontend_index(tmp_path: Path) -> None:
    settings = Settings(frontend_dist=build_frontend(tmp_path / "dist"))

    response = TestClient(create_app(settings)).get("/")

    assert response.status_code == 200
    assert "Lupus Ex Machina" in response.text


def test_frontend_bundles_are_served(tmp_path: Path) -> None:
    settings = Settings(frontend_dist=build_frontend(tmp_path / "dist"))

    response = TestClient(create_app(settings)).get("/assets/index.js")

    assert response.status_code == 200
    assert response.text == "export default 0\n"


def test_health_still_answers_when_the_frontend_is_mounted(tmp_path: Path) -> None:
    settings = Settings(frontend_dist=build_frontend(tmp_path / "dist"))

    response = TestClient(create_app(settings)).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_application_starts_without_a_frontend_build(tmp_path: Path) -> None:
    """Running the backend alone, against the Vite dev server, must stay possible."""
    settings = Settings(frontend_dist=tmp_path / "never-built")

    client = TestClient(create_app(settings))

    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 404
