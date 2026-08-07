"""The human player's two buttons (J5.6, D-014, D-048).

Absolute priority on the next turn, and the moderator's hand on how long the
debate may run. Both are read between turns, never inside one.
"""

from collections.abc import Sequence

from lupus_ex_machina.agents.scripted import (
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
    Wait,
)
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.runner import (
    DebateControl,
    FloorClaim,
)
from lupus_ex_machina.engine.runner.acting import apply
from lupus_ex_machina.engine.runner.day import play_day
from lupus_ex_machina.engine.runner.scribe import Scribe
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.turn import Turn
from lupus_ex_machina.engine.views import PlayerView
from support.agents import Insistent, VotesFor
from support.days import a_day_of, a_day_played_by
from support.games import (
    speakers_of,
)

# --- The human player's two buttons (J5.6, D-014) ----------------------------


async def test_asking_for_the_floor_the_ordinary_way_is_only_a_bid() -> None:
    """The human player's first button is a bid like any other (J5.6.1).

    The contrast with the second one is the whole of D-014: the same seat, with
    the same faint wish to speak, is passed over by the auction and served at
    once by the priority button. One asks, the other takes.
    """
    state = create_game(rng=create_rng(12))
    quiet = state.players[5].id
    urgencies = {seat: (0 if seat == 5 else 100) for seat in range(8)}

    _, asked = await a_day_of(urgencies)

    claim = FloorClaim()
    claim.claim(quiet)
    _, took = await a_day_of(urgencies, claim=claim)

    assert speakers_of(asked)[0] != quiet, "wanting it a little wins nothing"
    assert speakers_of(took)[0] == quiet, "the button owes the auction nothing"


async def test_the_priority_button_takes_the_next_turn_whatever_the_bids() -> None:
    """D-014: absolute priority, and it does not need to win anything."""
    state = create_game(rng=create_rng(12))
    quiet = state.players[5].id
    claim = FloorClaim()
    claim.claim(quiet)

    _, events = await a_day_of({seat: (0 if seat == 5 else 100) for seat in range(8)}, claim=claim)

    assert speakers_of(events)[0] == quiet


async def test_the_priority_button_never_cuts_a_turn_in_half() -> None:
    """It applies at the end of the turn under way, never inside it (D-014)."""
    state = create_game(rng=create_rng(12))
    quiet = state.players[5].id
    claim = FloorClaim()

    class ClaimsWhileSpeaking(Scripted):
        """Presses the button in the middle of somebody else's turn."""

        async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
            return Bid(urgency=100, intention="Parler.")

        async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
            claim.claim(quiet)
            return Turn(intent=TakeTurn(speech="Je finis ma phrase.") if view.may_speak else Wait())

    agents: dict[PlayerId, Agent] = {
        player.id: (Insistent(0) if player.id == quiet else ClaimsWhileSpeaking())
        for player in state.players
    }
    events = await a_day_played_by(agents, claim=claim)
    spoken = speakers_of(events)

    assert spoken[0] != quiet, "the turn under way was finished first"
    assert spoken[1] == quiet, "and the button was honoured at the next one"


def test_a_claim_is_spent_once_it_is_honoured() -> None:
    """Otherwise the button would hand its owner the floor for the rest of the day."""
    claim = FloorClaim()
    claim.claim(PlayerId("player-5"))

    assert claim.take() == PlayerId("player-5")
    assert claim.take() is None


def test_a_floor_nobody_claimed_is_nobody_s() -> None:
    assert FloorClaim().take() is None


async def test_a_claim_from_someone_who_can_no_longer_speak_is_dropped() -> None:
    """A button pressed about a turn that no longer exists changes nothing.

    Voting gives up the floor for the round (D-013), so the claim of a player
    who has voted has nothing to claim. Honoured anyway, it would hand the turn
    to someone the rules then refuse, and the debate would read that refusal as
    a table with nothing left to say (D-060) and call the vote early.
    """
    state = create_game(rng=create_rng(12))
    voted = state.players[5].id
    claim = FloorClaim()

    agents: dict[PlayerId, Agent] = {
        player.id: (VotesFor(None) if player.id == voted else Insistent(50))
        for player in state.players
    }
    scribe = Scribe(agents, journal := Journal(), create_rng(3))
    opened = scribe.enter(state, Phase.DAY, day=2)

    # That seat votes, gives up the floor, and only then presses the button.
    opened = apply(scribe, opened, voted, TakeTurn(vote=Vote()))
    claim.claim(voted)
    await play_day(scribe, opened, control=DebateControl(), claim=claim)

    spoken = speakers_of(journal.events)

    assert voted not in spoken, "it had given up the floor"
    assert spoken, "and the debate carried on without it"
