"""A client of a running application, already through the door (J8).

**Used as a context manager, always.** A `TestClient` built without one starts
and stops a portal for every single request, which cancels the task a game is
playing in: the game freezes wherever it was, and a test reading the traffic
gets a fraction of a game while believing it read all of one. Inside a block,
the loop lives for as long as the block does — which is what a real server does
for as long as it runs.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi.testclient import TestClient

from lupus_ex_machina.app import create_app
from lupus_ex_machina.config import Settings
from lupus_ex_machina.hosting import GameHost, HostedGame
from support.hosted import a_completions

PASSWORD = "ouvre-toi"

#: Six players, a pack made to leave with a victim, and a game watched from
#: outside. Short enough to play in a test, long enough to be a real game.
WATCHED: dict[str, Any] = {
    "rules": {
        "table": {"player_count": 6, "seed": 4},
        "night": {"require_werewolf_target": True},
    }
}

#: The same game, played from seat zero, with the dead learning nothing more —
#: which is what keeps a leak test meaningful past the first death (D-105).
PLAYED: dict[str, Any] = {
    "rules": {
        "table": {"player_count": 6, "seed": 4, "mode": "player", "human_seat": 0},
        "information": {"reveal_everything_to_the_dead": False},
        "night": {"require_werewolf_target": True},
    }
}


@contextmanager
def logged_in(*, playing: bool = False) -> Iterator[TestClient]:
    """A client through the door, of an application whose models reach nobody."""
    app = create_app(Settings(password=PASSWORD, secret_key="clef"), completions=a_completions())
    with TestClient(app) as client:
        client.post("/api/session", json={"password": PASSWORD})
        if playing:
            client.post("/api/game", json=PLAYED)
        yield client


def game_of(client: TestClient) -> HostedGame:
    """The game the application behind that client is hosting.

    Asserted rather than returned as an optional: a test that reached for a game
    that is not there wants to say so loudly, not to check for None.
    """
    host: GameHost = client.app.state.host  # type: ignore[attr-defined]
    hosted = host.current
    assert hosted is not None, "the application is hosting no game"
    return hosted
