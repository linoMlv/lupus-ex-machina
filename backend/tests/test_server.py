"""The console entry point wires the settings into the ASGI server."""

import pytest
import uvicorn
from fastapi import FastAPI

from lupus_ex_machina.server import main


@pytest.fixture
def recorded_run(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Capture the arguments the entry point passes to uvicorn."""
    recorded: dict[str, object] = {}

    def fake_run(app: FastAPI, **kwargs: object) -> None:
        recorded["app"] = app
        recorded.update(kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    return recorded


def test_main_serves_the_application_on_the_configured_address(
    recorded_run: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LUPUS_HOST", "0.0.0.0")  # a container binds every interface
    monkeypatch.setenv("LUPUS_PORT", "9123")
    monkeypatch.setenv("LUPUS_LOG_LEVEL", "warning")

    main()

    assert isinstance(recorded_run["app"], FastAPI)
    assert recorded_run["host"] == "0.0.0.0"
    assert recorded_run["port"] == 9123
    assert recorded_run["log_level"] == "warning"


def test_main_falls_back_to_the_default_address(
    recorded_run: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LUPUS_HOST", raising=False)
    monkeypatch.delenv("LUPUS_PORT", raising=False)

    main()

    assert recorded_run["host"] == "127.0.0.1"
    assert recorded_run["port"] == 8000
