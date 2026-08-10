"""Creating, starting, reading and giving up a game over HTTP (J8.2).

Every route here needs a session; that is proved once and for all by
`test_every_route_is_guarded`, so these tests come in already logged in and are
about the game rather than the door.
"""

from typing import Any

from fastapi.testclient import TestClient

from lupus_ex_machina.app import create_app
from lupus_ex_machina.config import Settings
from support.hosted import a_provider

PASSWORD = "ouvre-toi"

SHORT_GAME: dict[str, Any] = {
    "rules": {
        "table": {"player_count": 6, "seed": 4},
        "night": {"require_werewolf_target": True},
    }
}


def logged_in() -> TestClient:
    """A client of an application whose models answer without a network."""
    app = create_app(Settings(password=PASSWORD, secret_key="clef"), provider=a_provider)
    client = TestClient(app)
    client.post("/api/session", json={"password": PASSWORD})
    return client


def test_a_game_is_created_from_a_configuration() -> None:
    client = logged_in()

    response = client.post("/api/game", json=SHORT_GAME)

    assert response.status_code == 201
    assert response.json()["stage"] == "created"
    assert len(response.json()["players"]) == 6


def test_a_configuration_that_is_not_one_is_refused() -> None:
    """The schema is the single source of truth, so it is what refuses (D-068)."""
    client = logged_in()

    refused = client.post("/api/game", json={"rules": {"table": {"player_count": 42}}})

    assert refused.status_code == 422


def test_a_created_game_has_played_nothing() -> None:
    """D-103: creating deals the table, starting is what spends anything."""
    client = logged_in()

    created = client.post("/api/game", json=SHORT_GAME).json()

    assert created["stage"] == "created"
    assert created["outcome"] is None
    assert all(player["alive"] for player in created["players"])


def test_the_summary_of_a_game_never_carries_a_role() -> None:
    """Who sits where is public; what they were dealt is the whole game (D-009).

    The journal is projected before it is sent (J8.3); this one is a summary,
    and the way it stays safe is by holding nothing that needs projecting.
    """
    client = logged_in()
    client.post("/api/game", json=SHORT_GAME)
    client.post("/api/game/start")

    written = client.get("/api/game").text
    client.delete("/api/game")

    assert "werewolf" not in written
    assert "seer" not in written
    assert "witch" not in written
    assert "hunter" not in written


def test_starting_a_game_sets_it_playing() -> None:
    """Accepted rather than answered: a request that played a game would take an hour.

    That it plays itself *to an end* is proved where the life of a game lives,
    in tests/hosting — polling an HTTP route until it changes would put a clock
    in the suite for something already covered.
    """
    client = logged_in()
    client.post("/api/game", json=SHORT_GAME)

    started = client.post("/api/game/start")

    assert started.status_code == 202
    assert started.json()["stage"] == "playing"
    client.delete("/api/game")


def test_the_mode_is_the_one_the_game_was_dealt_with() -> None:
    """D-100: a client never asks for a mode, it is told the one of the game.

    There is nowhere in this API to ask for another — which is the point. A
    spectator is omniscient, so a mode chosen per client would let anyone open a
    second tab on a game they are playing. What each mode *shows* is proved
    where the projection lives (J8.3).
    """
    client = logged_in()
    player_mode = {
        "rules": {
            "table": {"player_count": 6, "seed": 4, "mode": "player", "human_seat": 0},
            "night": {"require_werewolf_target": True},
        }
    }

    created = client.post("/api/game", json=player_mode)

    assert created.json()["mode"] == "player"


def test_a_second_game_is_refused_while_one_stands() -> None:
    client = logged_in()
    client.post("/api/game", json=SHORT_GAME)

    refused = client.post("/api/game", json=SHORT_GAME)

    assert refused.status_code == 409


def test_a_game_is_given_up_and_the_place_reopens() -> None:
    client = logged_in()
    client.post("/api/game", json=SHORT_GAME)

    assert client.delete("/api/game").status_code == 204
    assert client.post("/api/game", json=SHORT_GAME).status_code == 201


def test_reading_a_game_that_does_not_exist_says_so() -> None:
    assert logged_in().get("/api/game").status_code == 404


def test_giving_up_a_game_that_does_not_exist_says_so() -> None:
    assert logged_in().delete("/api/game").status_code == 404


def test_starting_a_game_that_does_not_exist_says_so() -> None:
    assert logged_in().post("/api/game/start").status_code == 404


def test_a_game_cannot_be_started_twice() -> None:
    client = logged_in()
    client.post("/api/game", json=SHORT_GAME)
    client.post("/api/game/start")

    started_again = client.post("/api/game/start")
    client.delete("/api/game")

    assert started_again.status_code == 409


def test_no_game_can_be_created_without_a_provider_to_play_it() -> None:
    """Rather than a table dealt to nobody, and a failure discovered on start."""
    client = TestClient(create_app(Settings(password=PASSWORD, secret_key="clef")))
    client.post("/api/session", json={"password": PASSWORD})

    refused = client.post("/api/game", json=SHORT_GAME)

    assert refused.status_code == 503
    assert "LUPUS_LLM_API_KEY" in refused.json()["detail"]
