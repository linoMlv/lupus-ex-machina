"""A hosted game waits for whoever is watching it (J8.4.1, J8.4.2, J8.4.3).

The pieces are tested apart — the counter in `tests/engine/test_pacing.py`, the
two leads in `test_lead.py` — and this is them wired together: a game that runs
ahead of nobody stops, and one whose audience keeps up plays to its end.
"""

import asyncio

from lupus_ex_machina.configuration.schema import GameConfiguration
from lupus_ex_machina.engine.events import Event
from lupus_ex_machina.engine.rules import GameMode, GameRules, NightOptions, TableOptions
from lupus_ex_machina.hosting.stage import Stage
from support.hosted import SHORT_GAME, a_host

PLAYED = GameConfiguration(
    rules=GameRules(
        table=TableOptions(player_count=6, seed=4, mode=GameMode.PLAYER, human_seat=0),
        night=NightOptions(require_werewolf_target=True),
    )
)


async def test_a_game_nobody_watches_stops_rather_than_spending_the_budget() -> None:
    """The reason the pacing exists: turns nobody may ever see cost model calls."""
    game = a_host().create(SHORT_GAME)

    game.start()
    for _ in range(50):
        await asyncio.sleep(0)

    assert game.stage is Stage.PLAYING, "still going, but held"
    assert len(game.events) < 40, "it stopped early rather than playing most of a game"
    await game.abandon()


async def test_a_game_whose_audience_keeps_up_plays_to_its_end() -> None:
    """Paced is not stopped: a client that follows sees a whole game."""
    game = a_host().create(SHORT_GAME)

    with game.listening() as heard:

        async def keeping_up() -> None:
            while True:
                told = await heard.get()
                if told is None:
                    return
                if isinstance(told, Event):
                    game.hands.shown(told.sequence)

        game.start()
        watching = asyncio.ensure_future(keeping_up())
        await game.played()
        await asyncio.wait_for(watching, timeout=1)

    assert game.stage is Stage.OVER
    assert len(game.events) > 40, "a whole game, not the few turns of an unwatched one"


async def _played_until_it_waits(configuration: GameConfiguration) -> int:
    """How many facts a game gets through before its lead runs out."""
    game = a_host().create(configuration)
    game.start()
    for _ in range(80):
        await asyncio.sleep(0)
    written = len(game.events)
    await game.abandon()
    return written


async def test_a_played_game_runs_less_far_ahead_than_a_watched_one() -> None:
    """D-014 without ever throwing a turn away: there is never one to throw.

    Compared against a watched game rather than against a number, so that the
    two leads being made the same is what fails this — a fixed threshold would
    sit happily between them and prove nothing.
    """
    playing = await _played_until_it_waits(PLAYED)
    watching = await _played_until_it_waits(SHORT_GAME)

    assert 0 < playing < watching, "one turn in flight against three"
