"""J8.3.3 — the critical test: everything a player is sent, and nothing else.

The whole traffic of a whole game, captured and compared against the projection
of that game's journal. Stated that way it cannot be fooled by a name: a leak
under any field, in any fact, makes the two differ.

**Played with the dead kept in the dark** (D-105 off). Left on, the human becomes
the spectator the moment their character dies, and the assertion would be vacuous
from the first death onwards — the shape of hollow test this project has met
four times.

Three things are asserted before the comparison, for the same reason. That the
game ran to its end, so the capture is of a whole game rather than a corner of
one. That it produced facts a player must not see. And that it produced some
they must. A property over an empty set is true and worth nothing.
"""

from contextlib import suppress
from typing import Any

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from lupus_ex_machina.engine.journal import project_journal
from lupus_ex_machina.hosting.audience import recipient_for
from lupus_ex_machina.hosting.stage import Stage
from support.clients import game_of, logged_in


def everything_sent(client: TestClient) -> list[dict[str, Any]]:
    """Every fact that travelled to the client, over a whole game.

    Read until the server closes, which it does once the game has nothing more
    to say. Catching anything wider would let a broken socket read as a finished
    game, and the capture would fall silently short of what it is checking.
    """
    captured: list[dict[str, Any]] = []
    with client.websocket_connect("/api/game/stream") as stream, suppress(WebSocketDisconnect):
        while True:
            captured.extend(stream.receive_json()["events"])
    return captured


def test_a_player_is_sent_their_projection_and_not_one_fact_more() -> None:
    with logged_in(playing=True) as client:
        client.post("/api/game/start")

        sent = everything_sent(client)

        game = game_of(client)
        recorded = tuple(game.events)
        theirs = project_journal(recorded, recipient_for(game.state))

    assert game.stage is Stage.OVER, "a whole game, not a corner of one"
    assert len(recorded) > len(theirs), "the game produced facts this player may not see"
    assert theirs, "and some they may — comparing two empty lists proves nothing"
    assert [event["sequence"] for event in sent] == [event.sequence for event in theirs]
