"""The life of a hosted game: created, started, over (J8.2, D-101, D-103).

Creating and starting are two gestures (D-103). Creating deals the roles and
fixes the seed; until somebody starts it, nothing is played and no model is
asked anything — a game nobody is watching yet must not spend the call budget.

One game at a time (D-045, D-101): a second creation is refused rather than
quietly replacing the first, because the first is somebody's evening.
"""

import pytest

from lupus_ex_machina.configuration.schema import GameConfiguration
from lupus_ex_machina.engine.rules import GameRules, NightOptions, TableOptions
from lupus_ex_machina.engine.victory import Outcome
from lupus_ex_machina.hosting.errors import NoGameError, OneGameAtATimeError
from lupus_ex_machina.hosting.stage import Stage
from support.hosted import a_host, played_out

SHORT_GAME = GameConfiguration(
    rules=GameRules(
        table=TableOptions(player_count=6, seed=4),
        night=NightOptions(require_werewolf_target=True),
    )
)


def test_a_created_game_is_dealt_but_not_played() -> None:
    """D-103: creating deals the roles, starting is what spends anything."""
    host = a_host()

    game = host.create(SHORT_GAME)

    assert game.stage is Stage.CREATED
    assert game.players, "the table is dealt"
    assert list(game.events) == [], "and nothing has happened to it yet"


async def test_a_started_game_plays_itself_to_an_end() -> None:
    host = a_host()
    game = host.create(SHORT_GAME)

    await played_out(game)

    assert game.stage is Stage.OVER
    assert game.outcome in tuple(Outcome)
    assert game.events, "and it left a journal behind"


def test_a_second_game_is_refused_while_one_is_being_played() -> None:
    host = a_host()
    host.create(SHORT_GAME)

    with pytest.raises(OneGameAtATimeError):
        host.create(SHORT_GAME)


async def test_a_game_that_ended_leaves_the_place_to_the_next_one() -> None:
    """A finished game stays readable, and no longer stands in the way."""
    host = a_host()
    game = host.create(SHORT_GAME)
    await played_out(game)

    assert host.create(SHORT_GAME) is not game
    assert game.events, "and the one before is still there to read"


async def test_an_abandoned_game_leaves_the_place_too() -> None:
    host = a_host()
    host.create(SHORT_GAME)

    await host.abandon()

    assert host.current is None
    assert host.create(SHORT_GAME) is not None


async def test_abandoning_a_game_that_is_running_stops_it() -> None:
    """The place has to be free at once, not once the game feels like ending."""
    host = a_host()
    game = host.create(SHORT_GAME)
    game.start()

    await host.abandon()

    assert game.stage is Stage.ABANDONED


async def test_abandoning_nothing_says_so_rather_than_passing_silently() -> None:
    with pytest.raises(NoGameError):
        await a_host().abandon()


def test_the_host_starts_with_no_game_at_all() -> None:
    assert a_host().current is None


async def test_waiting_on_a_game_nobody_started_returns_at_once() -> None:
    """So a caller waiting for the end need not know whether it ever began."""
    game = a_host().create(SHORT_GAME)

    await game.played()

    assert game.stage is Stage.CREATED
