"""No route of the API answers without a session (J8.1.2, exit criterion 7).

The tests beside this one prove the door works. This one proves nobody built a
second door: it walks every route the application publishes and calls it with no
cookie, refusing any that answers. Anything open has to be on the list below
with its reason.

**Behaviour, not declaration.** An earlier version read the dependencies off the
route objects and found none at all — FastAPI wraps an included router rather
than flattening it — so it passed while reading nothing. Calling the route
cannot be hollow in that way, and it also catches a guard that is declared and
wrong.

Static mounts are out of scope and stay open by design: the front end is
JavaScript anybody may fetch, the GLB models are Kenney assets, and no
information about a game ever travels that way (D-046 keeps that true by
filtering before emission, never at the display).
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from lupus_ex_machina.app import create_app
from lupus_ex_machina.config import Settings

#: Routes that answer without a session, each with the reason.
OPEN: dict[str, str] = {
    "POST /api/session": "the door itself: it is what one has before having a session",
    "DELETE /api/session": "handing back a session one may no longer have is not a leak",
    "GET /health": "the container HEALTHCHECK and the platform probe, which hold no cookie",
}

#: What the guard sends. Enough to get past the shape of a request and reach the
#: question that matters: is a session required.
BODY: dict[str, Any] = {"password": "", "seed": 1}


def published() -> dict[str, list[str]]:
    """Every path the application publishes, with the methods it answers."""
    app = create_app(Settings(password="ouvre-toi", secret_key="clef"))
    return {
        path: [method.upper() for method in operations]
        for path, operations in app.openapi()["paths"].items()
    }


def answered_without_a_session() -> list[str]:
    """Every route that gives an answer to somebody who has no session."""
    client = TestClient(create_app(Settings(password="ouvre-toi", secret_key="clef")))
    return sorted(
        f"{method} {path}"
        for path, methods in published().items()
        for method in methods
        if client.request(method, path, json=BODY).status_code != 401
    )


def test_the_scan_finds_the_routes_at_all() -> None:
    """Without this the guard is true of the empty set, which is how it read first."""
    assert {"/health", "/api/session"} <= set(published())


def test_no_route_answers_without_a_session() -> None:
    unexplained = sorted(set(answered_without_a_session()) - set(OPEN))

    assert unexplained == [], (
        "these routes answer without a session: declare Depends(require_session) "
        "on them, or add them to OPEN with the reason they are open"
    )


def test_the_list_of_open_routes_has_not_outlived_the_code() -> None:
    """A list naming routes nobody serves any more stops being read."""
    declared = {f"{method} {path}" for path, methods in published().items() for method in methods}

    assert sorted(set(OPEN) - declared) == []


@pytest.mark.parametrize("route", sorted(OPEN))
def test_every_open_route_says_why_it_is_open(route: str) -> None:
    assert OPEN[route].strip()
