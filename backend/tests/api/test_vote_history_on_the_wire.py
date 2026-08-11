"""What a person reconnecting is handed of past counts (D-111, J8bis.0.5).

The rule takes a memory away from agents; leaving it in place on the wire would
hand the same thing back to the one player who has a screen, and turn D-017's
asymmetry of memory into a systematic advantage.

**The spectator is untouched**, and deliberately: they watch a game they are not
in and are omniscient by construction (D-046) — so does a player whose character
has died, when the rules allow it (D-105). D-111 is about what somebody still
*playing* may look up.
"""

from typing import Any

from fastapi.testclient import TestClient

from lupus_ex_machina.agents.scripted import RandomAgent
from lupus_ex_machina.engine.events import EventKind
from lupus_ex_machina.engine.rng import create_rng
from support.clients import followed_to_the_end, logged_in

#: A game played from seat zero, whose counts stop being readable once their
#: round has closed. The dead learn nothing more, so the capture keeps meaning
#: something past the first death (D-105).
FORGETFUL: dict[str, Any] = {
    "rules": {
        "table": {"player_count": 6, "seed": 4, "mode": "player", "human_seat": 0},
        "information": {
            "public_vote_history": False,
            "reveal_everything_to_the_dead": False,
        },
        "night": {"require_werewolf_target": True},
    }
}

#: The same game, watched from outside. Nothing is ever dropped for a spectator.
OVERSEEN: dict[str, Any] = {
    "rules": {
        "table": {"player_count": 6, "seed": 4},
        "information": {"public_vote_history": False},
        "night": {"require_werewolf_target": True},
    }
}


def counts_in(events: list[dict[str, Any]]) -> list[int]:
    """The days of every count that travelled."""
    return [
        event["day"] for event in events if event["payload"]["kind"] == EventKind.BALLOTS_REVEALED
    ]


def played_out(client: TestClient, configuration: dict[str, Any]) -> None:
    """Deal that game, start it, and let it run to its end."""
    client.post("/api/game", json=configuration)
    client.post("/api/game/start")
    followed_to_the_end(client, RandomAgent(rng=create_rng(4)))


def reconnected(client: TestClient) -> list[dict[str, Any]]:
    """Everything a client that has heard nothing is handed (D-102)."""
    with client.websocket_connect("/api/game/stream") as stream:
        return list(stream.receive_json()["events"])


def test_a_person_reconnecting_is_not_handed_a_count_they_may_no_longer_look_up() -> None:
    with logged_in() as client:
        played_out(client, FORGETFUL)

        caught_up = reconnected(client)

        last_day = max(event["day"] for event in caught_up)
        assert last_day >= 2, "the game must have gone past its first round to prove anything"
        assert counts_in(caught_up) in ([], [last_day])


def test_the_spectator_is_handed_the_whole_history_all_the_same() -> None:
    """Omniscient by construction: D-111 is about what a *player* may look up."""
    with logged_in() as client:
        played_out(client, OVERSEEN)

        caught_up = reconnected(client)

        assert len(set(counts_in(caught_up))) >= 2, "a spectator keeps every count of the game"
