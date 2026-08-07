"""What each of the three shapes of a turn actually does (J5.2.2, D-028).

Speaking, voting, or both at once — and the order the two halves are applied
in, which is a rule of the game rather than a detail (D-051).
"""

from collections.abc import Sequence

from lupus_ex_machina.agents.scripted import (
    Scripted,
)
from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.events import (
    Event,
    EventKind,
)
from lupus_ex_machina.engine.intents import (
    TakeTurn,
    Vote,
    Wait,
)
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.runner.acting import apply
from lupus_ex_machina.engine.runner.scribe import Scribe
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.turn import Turn
from lupus_ex_machina.engine.views import PlayerView

# --- What each of the three turns actually does (J5.2.2) ---------------------


class TakesOneTurn(Scripted):
    """Plays a turn written by the test on its first go, then waits for good."""

    def __init__(self, turn: TakeTurn) -> None:
        """Take the one turn this agent will play."""
        self._turn = turn
        self._played = False

    async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
        """Bid flatly: what this agent is for is what it does with the floor."""
        return Bid(urgency=50, intention="Jouer.")

    async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
        """Play the turn once, if the rules are offering it."""
        if self._played or not (view.may_speak or view.may_vote):
            return Turn(intent=Wait())
        self._played = True
        return Turn(intent=self._turn)


def one_turn_of(turn: TakeTurn) -> tuple[GameState, PlayerId, tuple[Event, ...]]:
    """Play a single day up to its resolution, one seat playing that turn."""
    state = create_game(rng=create_rng(11)).entering(Phase.DAY, day=2)
    actor = state.living[0].id
    journal = Journal()
    scribe = Scribe({actor: TakesOneTurn(turn)}, journal, create_rng(1))

    return apply(scribe, state, actor, turn), actor, journal.events


def kinds_of(events: tuple[Event, ...]) -> list[EventKind]:
    return [event.payload.kind for event in events]


def test_speaking_alone_leaves_the_round_open() -> None:
    after, actor, events = one_turn_of(TakeTurn(speech="Théo est bien silencieux."))

    assert EventKind.SPEECH_DELIVERED in kinds_of(events)
    assert not after.has_voted(actor), "the floor stays open"
    assert [speech.speaker for speech in after.floor] == [actor]


def test_voting_alone_closes_the_round_without_a_word() -> None:
    after, actor, events = one_turn_of(TakeTurn(vote=Vote()))

    assert EventKind.SPEECH_DELIVERED not in kinds_of(events)
    assert after.has_voted(actor)
    assert after.floor == (), "nothing was said, so the auction has nothing to weigh"


def test_speaking_and_voting_at_once_does_both_in_that_order() -> None:
    """Speech first, then the announcement (D-051).

    The other way round, the table would learn someone had voted before hearing
    the words that explain it.
    """
    after, actor, events = one_turn_of(
        TakeTurn(speech="J'ai assez entendu.", vote=Vote(target=None))
    )

    recorded = kinds_of(events)

    assert recorded.index(EventKind.SPEECH_DELIVERED) < recorded.index(EventKind.BALLOT_CAST)
    assert recorded.index(EventKind.BALLOT_CAST) < recorded.index(EventKind.BALLOT_ANNOUNCED)
    assert after.has_voted(actor)
    assert [speech.speaker for speech in after.floor] == [actor]


def test_a_turn_remembers_whom_it_addressed_and_accused() -> None:
    """What the next auction is scored against (D-002)."""
    state = create_game(rng=create_rng(11)).entering(Phase.DAY, day=2)
    speaker, target = state.living[0].id, state.living[1].id

    after, _, _ = one_turn_of(TakeTurn(speech="Théo, tu mens.", addressed=target, accused=target))

    assert after.floor[0].addressed == target
    assert after.floor[0].accused == target
    assert after.floor[0].speaker == speaker
