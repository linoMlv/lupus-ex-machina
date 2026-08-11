"""What a whole game actually hands its agents of past counts (D-111).

The filter has its own tests; this one asks the question that matters — whether
anything on the way to a player uses it. Written against a real game rather than
a hand-made journal, because the defect it guards against is a missing call, and
a missing call is invisible to a unit test of the thing that was never called.
"""

from collections.abc import Sequence

from lupus_ex_machina.agents.scripted import RandomAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.events import BallotsRevealed, Event
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameRules, InformationOptions
from lupus_ex_machina.engine.runner import play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.turn import Reflection, Turn
from lupus_ex_machina.engine.views import PlayerView

#: A seed whose game runs long enough for a count to become *past*. One round is
#: not enough: nothing is ever old on the day it happens.
LONG_ENOUGH = 4


class Overhearing:
    """A scripted agent that keeps every journal it was handed."""

    def __init__(self, played: Agent) -> None:
        """Wrap an agent that knows how to play, and listen in on its questions."""
        self._played = played
        self.handed: list[tuple[int, tuple[Event, ...]]] = []

    async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
        """Bid as the wrapped agent would, keeping what it was shown."""
        self._remember(view, journal)
        return await self._played.bid(view, journal)

    async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
        """Play as the wrapped agent would, keeping what it was shown."""
        self._remember(view, journal)
        return await self._played.decide(view, journal)

    async def reflect(self, view: PlayerView, journal: Sequence[Event]) -> Reflection:
        """Take stock as the wrapped agent would, keeping what it was shown."""
        self._remember(view, journal)
        return await self._played.reflect(view, journal)

    def _remember(self, view: PlayerView, journal: Sequence[Event]) -> None:
        self.handed.append((view.day, tuple(journal)))


def counts_older_than_the_day(handed: list[tuple[int, tuple[Event, ...]]]) -> list[int]:
    """The days of every count handed over after its own round had closed."""
    return [
        event.day
        for day, journal in handed
        for event in journal
        if isinstance(event.payload, BallotsRevealed) and event.day < day
    ]


def every_count_handed(handed: list[tuple[int, tuple[Event, ...]]]) -> list[int]:
    """The days of every count handed over at all, however fresh."""
    return [
        event.day
        for _, journal in handed
        for event in journal
        if isinstance(event.payload, BallotsRevealed)
    ]


async def played_with(information: InformationOptions) -> list[Overhearing]:
    """One whole game under those rules, with every agent listening in."""
    rng = create_rng(LONG_ENOUGH)
    state = create_game(GameRules(information=information), rng=rng)
    listening = [Overhearing(RandomAgent(rng=rng)) for _ in state.players]
    agents: dict[PlayerId, Agent] = {
        player.id: agent for player, agent in zip(state.players, listening, strict=True)
    }
    await play_game(state, agents)
    return listening


async def test_no_agent_is_handed_the_count_of_a_round_that_has_closed() -> None:
    listening = await played_with(InformationOptions(public_vote_history=False))
    handed = [given for agent in listening for given in agent.handed]

    assert every_count_handed(handed), "the game must produce counts for this to prove anything"
    assert counts_older_than_the_day(handed) == []


async def test_the_option_left_standing_hands_the_whole_history_over() -> None:
    """The other half of the property: without it, nothing is dropped."""
    listening = await played_with(InformationOptions(public_vote_history=True))
    handed = [given for agent in listening for given in agent.handed]

    assert counts_older_than_the_day(handed), "past counts must reach agents when the option stands"
