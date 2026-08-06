"""Playing a game with agents whose answers have to be awaited (D-087).

A model answers over a network, so the engine has to be able to wait for it
without holding anything up. That is a property of the loop rather than of the
rules, and it is checked here on an agent that suspends before every answer —
the cheapest stand-in for the latency J7 is about to introduce.
"""

import asyncio

from lupus_ex_machina.agents.scripted import Scripted
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.intents import (
    Intent,
    IntentKind,
    PriorityPoint,
    RoleAction,
    SharePriority,
    TakeTurn,
    Vote,
    Wait,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameRules
from lupus_ex_machina.engine.runner import play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.turn import Turn
from lupus_ex_machina.engine.views import PlayerView


class AwaitedAgent(Scripted):
    """Names the first player it may name, but only after suspending.

    Deliberately written out rather than wrapped around a scripted agent: what
    is under test is that the engine awaits an answer, so the answer has to come
    from something that genuinely suspends before giving it.
    """

    def __init__(self) -> None:
        """Start with nothing asked of it yet."""
        self.answers = 0

    async def bid(self, view: PlayerView) -> Bid:
        """Want the floor, after letting the loop run something else."""
        await asyncio.sleep(0)
        self.answers += 1
        return Bid(urgency=100, intention="Accuser.")

    async def decide(self, view: PlayerView) -> Turn:
        """Play the first legal move on offer, after suspending."""
        await asyncio.sleep(0)
        self.answers += 1
        return Turn(intent=self._move(view))

    @staticmethod
    def _move(view: PlayerView) -> Intent:
        if IntentKind.ROLE_ACTION in view.allowed_intents and view.action_targets:
            return RoleAction(action=view.available_actions[0], target=view.action_targets[0])
        if IntentKind.SHARE_PRIORITY in view.allowed_intents and view.action_targets:
            return SharePriority(
                allocations=(
                    PriorityPoint(target=view.action_targets[0], points=view.priority_budget),
                )
            )
        if view.may_vote:
            return TakeTurn(vote=Vote(target=view.vote_targets[0] if view.vote_targets else None))
        return Wait()


class Gauge:
    """How many answers were in flight at the same moment.

    The peak is the whole measurement: asked one after another, it never leaves
    one, whatever the table size.
    """

    def __init__(self) -> None:
        """Start with nothing in flight."""
        self.in_flight = 0
        self.peak = 0

    async def measure(self) -> None:
        """Count oneself in, hand the loop back, then count oneself out."""
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        await asyncio.sleep(0)
        self.in_flight -= 1


class MeasuredAgent(AwaitedAgent):
    """An agent that reports how many of its peers were bidding alongside it."""

    def __init__(self, gauge: Gauge) -> None:
        """Take the gauge every seat at this table shares."""
        super().__init__()
        self._gauge = gauge

    async def bid(self, view: PlayerView) -> Bid:
        """Bid, through the gauge."""
        await self._gauge.measure()
        return await super().bid(view)


async def test_the_bids_of_one_auction_are_asked_all_at_once() -> None:
    """The floor is auctioned in one round trip, not in one per player (GL-7).

    Bidding is the call a game makes most often — about seven per turn at the
    floor — so asking in sequence would add up seven latencies where one is
    enough, and that is the whole of the budget the display was meant to hide.
    """
    gauge = Gauge()
    state = create_game(GameRules(), rng=create_rng(3))
    agents: dict[PlayerId, Agent] = {player.id: MeasuredAgent(gauge) for player in state.players}

    await play_game(state, agents, rng=create_rng(3))

    # Day 1 opens with nobody having spoken, so the whole table is asked at once.
    assert gauge.peak == len(state.players)


async def test_a_whole_game_is_played_by_agents_that_answer_asynchronously() -> None:
    rng = create_rng(3)
    state = create_game(GameRules(), rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: AwaitedAgent() for player in state.players}

    result = await play_game(state, agents, rng=rng)

    assert result.state.phase is Phase.ENDED
    assert result.rounds >= 1
    # Somebody died, so the moves these agents awaited were applied rather than
    # merely accepted: a coroutine taken for an intent kills nobody.
    assert any(not player.alive for player in result.state.players)


async def test_every_seat_is_actually_asked_something() -> None:
    """Guard the test above: a game nobody was asked about would prove nothing."""
    rng = create_rng(3)
    state = create_game(GameRules(), rng=rng)
    agents = {player.id: AwaitedAgent() for player in state.players}

    await play_game(state, dict(agents), rng=rng)

    assert all(agent.answers > 0 for agent in agents.values())
