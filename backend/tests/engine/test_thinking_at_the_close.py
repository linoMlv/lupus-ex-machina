"""Thinking once more when the round closes (D-086)."""

from collections.abc import Sequence

from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.events import (
    Event,
    PrivateReasoningRecorded,
    VoteResolved,
)
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameRules
from lupus_ex_machina.engine.runner import GameResult, play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.turn import (
    Reflection,
)
from lupus_ex_machina.engine.validation import BOOTSTRAP_DAY
from lupus_ex_machina.engine.views import PlayerView
from support.thinkers import (
    ThinkingAgent,
)

# --- Thinking once more when the round closes (D-086) ------------------------

CLOSING_THOUGHT = "Le dépouillement change tout ce que je croyais."


class ThinksAgainAtTheClose(ThinkingAgent):
    """Thinks on its turn like any agent, and once more when the round closes."""

    async def reflect(self, view: PlayerView, journal: Sequence[Event]) -> Reflection:
        """Take stock of what the count and the resolution just taught."""
        return Reflection(reasoning=CLOSING_THOUGHT)


async def a_game_of_second_thoughts() -> GameResult:
    """A whole game where every seat thinks again at every close."""
    rng = create_rng(3)
    state = create_game(GameRules(), rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: ThinksAgainAtTheClose() for player in state.players}
    return await play_game(state, agents, rng=rng)


async def test_a_player_who_has_voted_thinks_again_when_the_round_closes() -> None:
    """D-086: voting ends the floor, not the thinking.

    The moment is chosen rather than incidental — the count and the resolution
    are what teaches a player the most in a whole round.
    """
    result = await a_game_of_second_thoughts()

    closing = [
        event
        for event in result.journal
        if isinstance(event.payload, PrivateReasoningRecorded)
        and event.payload.reasoning == CLOSING_THOUGHT
    ]

    assert closing, "nobody took stock at the close"


async def test_taking_stock_happens_after_the_count_rather_than_before() -> None:
    """Asked any earlier, it would be a second turn rather than a second thought."""
    result = await a_game_of_second_thoughts()
    counted = next(
        event.sequence for event in result.journal if isinstance(event.payload, VoteResolved)
    )
    took_stock = next(
        event.sequence
        for event in result.journal
        if isinstance(event.payload, PrivateReasoningRecorded)
        and event.payload.reasoning == CLOSING_THOUGHT
    )

    assert took_stock > counted


async def test_every_living_player_takes_stock_at_the_close() -> None:
    """Everyone at the table has voted by then, so everyone is asked (D-013).

    Day 1 is where the whole table is still there: its only legal vote is a
    blank one (D-032), so the round closes without eliminating anybody.
    """
    result = await a_game_of_second_thoughts()

    took_stock = {
        event.payload.player
        for event in result.journal
        if isinstance(event.payload, PrivateReasoningRecorded)
        and event.payload.reasoning == CLOSING_THOUGHT
        and event.day == BOOTSTRAP_DAY
    }

    assert len(took_stock) == len(result.state.players)
