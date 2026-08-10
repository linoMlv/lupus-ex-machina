"""A paced game waits for its audience, between turns (J8.4.1, J8.4.2).

The pacing of the previous file is a counter; this is it holding a real game
back. Both the day and the night are paced, because a night turn is a model call
like any other and an unwatched night would spend the budget just as fast.
"""

import asyncio

from lupus_ex_machina.agents.scripted import RandomAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameRules, NightOptions, TableOptions
from lupus_ex_machina.engine.runner import play_game
from lupus_ex_machina.engine.runner.controls import Pacing
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState

SHORT = GameRules(
    table=TableOptions(player_count=6, seed=4),
    night=NightOptions(require_werewolf_target=True),
)


def a_game() -> tuple[GameState, dict[PlayerId, Agent], Journal]:
    rng = create_rng(SHORT.table.seed)
    state = create_game(SHORT, rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: RandomAgent(rng=rng) for player in state.players}
    return state, agents, Journal()


async def test_a_paced_game_stops_once_nobody_has_caught_up() -> None:
    """The budget of a game nobody watches is the whole reason this exists."""
    state, agents, journal = a_game()
    pacing = Pacing(turns_in_flight=2)

    playing = asyncio.ensure_future(play_game(state, agents, journal=journal, pacing=pacing))
    for _ in range(20):
        await asyncio.sleep(0)

    assert not playing.done(), "the game is waiting on an audience"
    held_at = len(journal)

    playing.cancel()
    assert held_at < 40, "and it stopped early rather than playing most of a game"


async def test_an_audience_that_keeps_up_lets_the_game_finish() -> None:
    """Paced is not stopped: a client that follows sees a whole game."""
    state, agents, journal = a_game()
    pacing = Pacing(turns_in_flight=2)

    async def keeping_up() -> None:
        while True:
            pacing.shown(len(journal))
            await asyncio.sleep(0)

    watching = asyncio.ensure_future(keeping_up())
    result = await play_game(state, agents, journal=journal, pacing=pacing)
    watching.cancel()

    assert result.rounds > 0
    assert len(journal) > 40, "a whole game, not the two turns of an unwatched one"


async def test_a_game_nobody_paces_plays_straight_through() -> None:
    """Which is every scripted game, `make play`, and the whole suite."""
    state, agents, journal = a_game()

    result = await play_game(state, agents, journal=journal)

    assert result.rounds > 0
