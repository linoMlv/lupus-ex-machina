"""What a player is still allowed to re-read of past ballots (D-111).

The option was declared to the user in J6 and nothing read it, so past ballots
reached every agent whatever it was set to. What it now decides: set to false,
the detail of *who voted for whom* is dropped from what a player is handed for
rounds that are over — the outcome and the blank votes stay.

The rule is about **memory**, not about entitlement. Everyone was allowed to see
that count when it happened; what is taken away is the ability to look it up
again, so an agent has to remember through its notebook instead (D-005).
"""

from datetime import UTC, datetime

from lupus_ex_machina.engine.events import (
    BallotAnnounced,
    BallotCast,
    BallotsRevealed,
    Event,
    EventPayload,
    RevealedBallot,
    VoteResolved,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.recollection import recollected
from lupus_ex_machina.engine.rules import InformationOptions

FORGETS = InformationOptions(public_vote_history=False)
REMEMBERS = InformationOptions(public_vote_history=True)

ADELE, THELMA, CAMILLE = PlayerId("adele"), PlayerId("thelma"), PlayerId("camille")


def an_event(payload: EventPayload, *, day: int, sequence: int = 0) -> Event:
    """One fact, placed on the day it happened."""
    return Event(
        sequence=sequence,
        recorded_at=datetime(2026, 8, 11, tzinfo=UTC),
        phase=Phase.DAY,
        day=day,
        payload=payload,
    )


def a_count(voter: PlayerId, target: PlayerId, *, day: int, sequence: int = 0) -> Event:
    """A count read out to the table on that day."""
    return an_event(
        BallotsRevealed(ballots=(RevealedBallot(voter=voter, target=target),)),
        day=day,
        sequence=sequence,
    )


def counts_in(journal: tuple[Event, ...]) -> list[int]:
    """The days whose count is still readable in that journal."""
    return [event.day for event in journal if isinstance(event.payload, BallotsRevealed)]


def test_the_count_of_a_past_round_is_not_handed_over_again() -> None:
    journal = (
        a_count(ADELE, THELMA, day=1, sequence=0),
        a_count(THELMA, CAMILLE, day=2, sequence=1),
    )
    assert counts_in(journal) == [1, 2], "the journal must hold both counts to prove anything"

    kept = recollected(journal, day=2, information=FORGETS)

    assert counts_in(kept) == [2]


def test_the_count_of_the_round_in_progress_is_left_alone() -> None:
    """It is a moment of play (D-082) and the staging rests on it (D-075)."""
    journal = (a_count(ADELE, THELMA, day=3, sequence=0),)

    kept = recollected(journal, day=3, information=FORGETS)

    assert counts_in(kept) == [3]


def test_what_the_round_came_to_is_never_forgotten() -> None:
    """Who was eliminated is a fact of the game, visible on the square."""
    journal = (
        a_count(ADELE, THELMA, day=1, sequence=0),
        an_event(VoteResolved(eliminated=THELMA), day=1, sequence=1),
    )

    kept = recollected(journal, day=4, information=FORGETS)

    assert [type(event.payload) for event in kept] == [VoteResolved]


def test_a_blank_vote_stays_public_however_old_it_is() -> None:
    """Public the instant it is cast (D-027); hiding it later would reverse that."""
    journal = (
        an_event(BallotCast(voter=ADELE), day=1, sequence=0),
        an_event(BallotAnnounced(voter=THELMA), day=1, sequence=1),
    )

    kept = recollected(journal, day=4, information=FORGETS)

    assert [type(event.payload) for event in kept] == [BallotCast, BallotAnnounced]


def test_a_player_keeps_the_ballot_they_cast_themselves() -> None:
    """They wrote it, and it cannot be taken back (D-024)."""
    journal = (an_event(BallotCast(voter=ADELE, target=THELMA), day=1, sequence=0),)

    kept = recollected(journal, day=4, information=FORGETS)

    assert [type(event.payload) for event in kept] == [BallotCast]


def test_nothing_is_dropped_while_the_option_stands() -> None:
    journal = (
        a_count(ADELE, THELMA, day=1, sequence=0),
        a_count(THELMA, CAMILLE, day=2, sequence=1),
    )

    kept = recollected(journal, day=4, information=REMEMBERS)

    assert counts_in(kept) == [1, 2]
