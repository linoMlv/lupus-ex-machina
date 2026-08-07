"""Scripted seats several test modules play a debate with.

Each one does exactly one thing, so a test that uses it reads as the situation
it sets up rather than as the behaviour of an agent.
"""

from collections.abc import Sequence

from lupus_ex_machina.agents.scripted import Scripted
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.events import Event
from lupus_ex_machina.engine.intents import TakeTurn, Vote, Wait
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.turn import Turn
from lupus_ex_machina.engine.views import PlayerView


class Insistent(Scripted):
    """Wants the floor as much as the scale allows, and says so at length."""

    def __init__(self, urgency: int) -> None:
        """Take how badly this seat wants to speak."""
        self._urgency = urgency

    async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
        """Always bid the same, so a test can reason about the order."""
        return Bid(urgency=self._urgency, intention="Parler.")

    async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
        """Speak while the floor is open, then vote blank to close the round."""
        if view.may_speak:
            return Turn(intent=TakeTurn(speech="Je prends la parole."))
        return Turn(intent=TakeTurn(vote=Vote()) if view.may_vote else Wait())


class VotesFor(Scripted):
    """Votes for whoever the test names, and never says a word."""

    def __init__(self, target: PlayerId | None) -> None:
        """Take the player this seat always names."""
        self._target = target

    async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
        """Bid low: this seat is here to vote, not to argue."""
        return Bid(urgency=10, intention="Voter.")

    async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
        """Name that player when the rules still offer them, otherwise vote blank."""
        if not view.may_vote:
            return Turn(intent=Wait())
        wanted = self._target if self._target in view.vote_targets else None
        return Turn(intent=TakeTurn(vote=Vote(target=wanted)))


class NeverVotesAgent(Scripted):
    """Waits forever: legal (D-048), and a way to stall a round."""

    async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
        """Bid flatly: what this agent is for is what it does with the floor."""
        return Bid(urgency=50, intention="Jouer.")

    async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
        """Never do anything."""
        return Turn(intent=Wait())


def a_table_of(agent: type) -> dict[PlayerId, Agent]:
    """A whole table playing the same scripted seat."""
    return {player.id: agent() for player in create_game(rng=create_rng(12)).players}
