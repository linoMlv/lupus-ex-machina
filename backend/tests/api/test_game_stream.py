"""Following a game in real time (J8.3).

The websocket carries the whole of what a game produces, so it cannot borrow the
protection of the HTTP routes: it checks the session itself (J8.1.2).

A client says the last sequence it heard and is sent what follows — one path for
a first connection and a reconnection alike, which is what leaves no gap between
reading a history and subscribing to what comes next (D-102).

What a *player* is sent, as opposed to everything, is the critical test next
door.
"""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from lupus_ex_machina.app import create_app
from lupus_ex_machina.config import Settings
from lupus_ex_machina.hosting.protocol import PROTOCOL_VERSION
from support.clients import PASSWORD, WATCHED, logged_in


def test_the_stream_is_closed_to_anyone_without_a_session() -> None:
    """Authenticating the routes protects none of the traffic that matters."""
    application = create_app(Settings(password=PASSWORD, secret_key="clef"))
    with (
        TestClient(application) as client,
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/api/game/stream") as stream,
    ):
        stream.receive_json()


def test_the_stream_is_refused_when_there_is_no_game() -> None:
    with (
        logged_in() as client,
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/api/game/stream") as stream,
    ):
        stream.receive_json()


def test_a_listener_is_sent_what_the_game_has_recorded_so_far() -> None:
    """A first connection is a catch-up from nothing heard (D-102)."""
    with logged_in() as client:
        client.post("/api/game", json=WATCHED)
        client.post("/api/game/start")

        with client.websocket_connect("/api/game/stream") as stream:
            sent = stream.receive_json()

        assert sent["version"] == PROTOCOL_VERSION
        assert sent["events"], "the game had already opened before anybody connected"


def test_a_listener_is_sent_only_what_follows_the_sequence_it_declares() -> None:
    """The same path for a reconnection: say where you were, get the rest."""
    with logged_in() as client:
        client.post("/api/game", json=WATCHED)
        client.post("/api/game/start")

        with client.websocket_connect("/api/game/stream") as stream:
            heard = stream.receive_json()["events"]
        seen_up_to = heard[2]["sequence"]

        with client.websocket_connect(f"/api/game/stream?since={seen_up_to}") as stream:
            again = stream.receive_json()["events"]

        assert [event["sequence"] for event in again[:3]] == [
            seen_up_to + step for step in (1, 2, 3)
        ]


def test_the_stream_closes_itself_once_the_game_is_over() -> None:
    """A client with no way to know is a client holding the line for ever."""
    with logged_in() as client:
        client.post("/api/game", json=WATCHED)
        client.post("/api/game/start")

        with pytest.raises(WebSocketDisconnect):
            _read_until_closed(client)


def _read_until_closed(client: TestClient) -> None:
    """Read the stream until the server hangs up, which is what is under test."""
    with client.websocket_connect("/api/game/stream") as stream:
        while True:
            stream.receive_json()
