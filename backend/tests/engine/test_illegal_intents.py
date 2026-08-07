"""What the runner does with an intent the rules will not take.

A refused intent costs its author a turn and nothing else: it never reaches
the state, and the table never learns that somebody fumbled (D-001).
"""

from collections.abc import Sequence

import pytest

from lupus_ex_machina.agents.scripted import (
    AlwaysAccuseAgent,
    RandomAgent,
    RogueAgent,
    Scripted,
)
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.events import (
    Event,
)
from lupus_ex_machina.engine.intents import (
    TakeTurn,
    Vote,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import Rng, create_rng
from lupus_ex_machina.engine.runner import (
    play_game,
)
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.turn import Turn
from lupus_ex_machina.engine.views import PlayerView
from support.agents import NeverVotesAgent
from support.games import (
    assert_properly_finished,
    six_seats,
)

# --- Illegal intents --------------------------------------------------------


async def test_an_agent_playing_illegal_intents_cannot_break_a_game() -> None:
    """The engine owns legality: a refused intent costs a turn, nothing else (D-001).

    One deranged player among sane ones — which is exactly what a misbehaving
    model will look like in J7.
    """
    rng = create_rng(9)
    state = create_game(rng=rng)
    agents: dict[PlayerId, Agent] = {
        player.id: RogueAgent() if player.seat == 0 else RandomAgent(rng=rng)
        for player in state.players
    }

    result = await play_game(state, agents)

    assert_properly_finished(result)
    assert result.rejected_intents > 0


class TooEagerOnNightZeroAgent(Scripted):
    """Takes the floor on Night 0, where nothing but waiting is legal. Sane after."""

    def __init__(self, rng: Rng) -> None:
        """Take the generator the sane half of this agent draws from."""
        self._sane = RandomAgent(rng=rng)

    async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
        """Bid flatly: what this agent is for is what it does with the floor."""
        return Bid(urgency=50, intention="Jouer.")

    async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
        """Speak out of turn on Night 0, then play normally."""
        if view.phase is Phase.NIGHT_ZERO:
            return Turn(intent=TakeTurn(speech="Je prends la parole trop tôt."))
        return await self._sane.decide(view, journal)


async def test_an_illegal_intent_on_night_zero_is_counted_as_refused() -> None:
    """Night 0 collects an intent from everyone, so it must judge them too (D-032).

    Dropping the illegal ones silently would leave `rejected_intents` — which the
    console command prints as "intentions refusées par le moteur" — quietly wrong
    about the one phase where every agent is asked and nothing is allowed.
    """
    rng = create_rng(13)
    state = create_game(six_seats(), rng=rng)
    agents: dict[PlayerId, Agent] = {
        player.id: TooEagerOnNightZeroAgent(rng) for player in state.players
    }

    result = await play_game(state, agents)

    assert result.rejected_intents >= len(state.players)


async def test_a_player_who_never_votes_does_not_stall_the_round() -> None:
    """Waiting forever is legal, so the round needs its own way out (D-048, D-060)."""
    state = create_game(rng=create_rng(10))
    agents: dict[PlayerId, Agent] = {
        player.id: NeverVotesAgent() if player.seat == 0 else AlwaysAccuseAgent()
        for player in state.players
    }

    result = await play_game(state, agents)

    assert_properly_finished(result)


async def test_the_engine_refuses_to_loop_forever() -> None:
    """The round budget is a safety net, not a rule: exceeding it is a bug."""

    class ImmortalAgent(Scripted):
        async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
            return Bid(urgency=50, intention="Voter.")

        async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
            return Turn(intent=TakeTurn(vote=Vote()))  # nobody ever dies

    state = create_game(six_seats(), rng=create_rng(11))
    agents: dict[PlayerId, Agent] = {player.id: ImmortalAgent() for player in state.players}

    with pytest.raises(RuntimeError, match="did not end"):
        await play_game(state, agents, max_rounds=5)
