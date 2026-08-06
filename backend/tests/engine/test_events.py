"""Facts, and the audience each one is addressed to.

The whole information model rests on one property: a fact cannot exist without
declaring who may know it (D-009). That is checked here in two ways — a type
that forgets to declare an audience cannot even be built, and the audience of
every fact in the catalogue is pinned by an exhaustive table.

The table is the part that matters. Coverage cannot protect these values: a
wrong audience is a leak that runs perfectly.
"""

from datetime import UTC, datetime
from typing import get_args

import pytest
from pydantic import ValidationError

from lupus_ex_machina.engine.bidding import BidScore
from lupus_ex_machina.engine.events import (
    BallotAnnounced,
    BallotCast,
    BallotsRevealed,
    Event,
    EventPayload,
    Fact,
    FloorAuctioned,
    FloorClaimed,
    ForcedVoteReason,
    GameEnded,
    IntentRejected,
    NightPowerUsed,
    NightResolved,
    NotebookEntryDropped,
    NotebookEntryRecorded,
    PackRevealed,
    PhaseEntered,
    PlayerSeated,
    PowerSpent,
    PrioritiesRevealed,
    PriorityShared,
    PrivateReasoningRecorded,
    RevealedBallot,
    RevealedShare,
    RoleAssigned,
    RoleRevealed,
    RunoffOpened,
    SeerFindingAnnounced,
    SeerInspected,
    ShotFired,
    SpeechDelivered,
    VoteForced,
    VoteResolved,
)
from lupus_ex_machina.engine.intents import PriorityPoint
from lupus_ex_machina.engine.night import Revelation
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import RoleActionName, RoleName
from lupus_ex_machina.engine.victory import Outcome
from lupus_ex_machina.engine.visibility import SPECTATOR, Recipient, Visibility

WOLF = PlayerId("p0")
VILLAGER = PlayerId("p2")

WHEN = datetime(2026, 8, 3, 21, 0, tzinfo=UTC)

PACK = Visibility.for_role(RoleName.WEREWOLF)

A_FEW_POINTS = PriorityPoint(target=VILLAGER, points=60)
A_SPREAD = RevealedShare(wolf=WOLF, allocations=(A_FEW_POINTS,))
A_FINDING = Revelation(role=RoleName.WEREWOLF)

SEER = PlayerId("p4")


#: Every fact the engine can produce, next to the audience it is addressed to.
#: Changing a line of this table changes who knows what, which is why the table
#: is written out rather than derived.
AUDIENCES: list[tuple[EventPayload, Visibility]] = [
    (PlayerSeated(player=WOLF, name="Adèle", seat=0), Visibility.public()),
    (RoleAssigned(player=WOLF, role=RoleName.WEREWOLF), Visibility.for_player(WOLF)),
    (PackRevealed(members=(WOLF,)), PACK),
    (PhaseEntered(phase=Phase.DAY, day=2), Visibility.public()),
    (SpeechDelivered(speaker=WOLF, speech="Je me méfie de Camille."), Visibility.public()),
    (BallotCast(voter=WOLF, target=VILLAGER), Visibility.for_player(WOLF)),
    (BallotCast(voter=WOLF, target=None), Visibility.public()),
    (BallotAnnounced(voter=WOLF), Visibility.public()),
    (
        NightPowerUsed(actor=SEER, action=RoleActionName.INSPECT, target=WOLF),
        Visibility.for_player(SEER),
    ),
    (ShotFired(hunter=WOLF, target=VILLAGER, chosen_by_the_hunter=True), Visibility.public()),
    (
        PowerSpent(actor=WOLF, action=RoleActionName.POISON),
        Visibility.for_player(WOLF),
    ),
    (
        SeerInspected(seer=SEER, target=WOLF, revelation=A_FINDING),
        Visibility.for_player(SEER),
    ),
    (SeerFindingAnnounced(revelation=A_FINDING), Visibility.public()),
    (PriorityShared(actor=WOLF, allocations=(A_FEW_POINTS,)), Visibility.for_player(WOLF)),
    (PrioritiesRevealed(shares=(A_SPREAD,)), PACK),
    (RunoffOpened(targets=(VILLAGER,)), PACK),
    (VoteResolved(eliminated=VILLAGER), Visibility.public()),
    (NightResolved(victims=(VILLAGER,)), Visibility.public()),
    (RoleRevealed(player=VILLAGER, role=RoleName.VILLAGER), Visibility.public()),
    (IntentRejected(actor=WOLF, reason="dead players cannot act"), Visibility.spectator_only()),
    (GameEnded(outcome=Outcome.VILLAGE_WINS), Visibility.public()),
    (
        PrivateReasoningRecorded(player=WOLF, reasoning="Camille me soupçonne."),
        Visibility.for_player(WOLF),
    ),
    (
        NotebookEntryRecorded(player=WOLF, entry=0, note="Camille pivote vite."),
        Visibility.for_player(WOLF),
    ),
    (NotebookEntryDropped(player=WOLF, entry=0), Visibility.for_player(WOLF)),
    (
        FloorAuctioned(scores=(BidScore(bidder=WOLF, urgency=70),), winner=WOLF),
        Visibility.spectator_only(),
    ),
    (VoteForced(reason=ForcedVoteReason.DEBATE_EXHAUSTED), Visibility.public()),
    (
        BallotsRevealed(ballots=(RevealedBallot(voter=WOLF, target=VILLAGER),)),
        Visibility.public(),
    ),
    (FloorClaimed(player=WOLF), Visibility.public()),
]


def payload_types() -> set[type]:
    """Every concrete payload the union is made of."""
    union, _annotation = get_args(EventPayload)
    return set(get_args(union))


@pytest.mark.parametrize(("payload", "expected"), AUDIENCES, ids=lambda value: str(value)[:60])
def test_every_fact_is_addressed_to_the_declared_audience(
    payload: EventPayload, expected: Visibility
) -> None:
    assert payload.audience == expected


def test_the_table_covers_every_kind_of_fact() -> None:
    """Adding a fact without deciding who may know it must fail here.

    Without this, a new event type would default to whatever its author wrote
    and no test would ever disagree.
    """
    assert {type(payload) for payload, _ in AUDIENCES} == payload_types()


def test_a_fact_that_declares_no_audience_cannot_be_built() -> None:
    """The guarantee is structural, not a convention to remember."""

    class Unlabelled(Fact):
        """A fact whose author forgot to say who may know it."""

    with pytest.raises(TypeError, match="audience"):
        Unlabelled()  # type: ignore[abstract]


# --- What the audiences mean -------------------------------------------------


def test_a_named_ballot_reaches_its_author_and_nobody_else() -> None:
    """A voter may re-read their own vote; the table may not (D-013)."""
    ballot = BallotCast(voter=WOLF, target=VILLAGER)

    assert ballot.audience.reaches(Recipient(player=WOLF, role=RoleName.WEREWOLF))
    assert not ballot.audience.reaches(Recipient(player=VILLAGER, role=RoleName.VILLAGER))
    assert ballot.audience.reaches(SPECTATOR)


def test_a_blank_ballot_is_public_the_moment_it_is_cast() -> None:
    """Skipping costs the floor *and* reveals the choice (D-027)."""
    assert BallotCast(voter=WOLF, target=None).audience == Visibility.public()


def test_death_is_public_whatever_took_the_player() -> None:
    """Never configurable — only the role of the deceased may stay hidden (D-072)."""
    assert VoteResolved(eliminated=VILLAGER).audience == Visibility.public()
    assert NightResolved(victims=(VILLAGER,)).audience == Visibility.public()


def test_the_pack_channel_never_leaves_the_pack() -> None:
    villager = Recipient(player=VILLAGER, role=RoleName.VILLAGER)

    for spoken in (
        PriorityShared(actor=WOLF, allocations=(A_FEW_POINTS,)),
        PrioritiesRevealed(shares=(A_SPREAD,)),
        RunoffOpened(targets=(VILLAGER,)),
        PackRevealed(members=(WOLF,)),
    ):
        assert not spoken.audience.reaches(villager)


def test_a_spread_is_its_own_wolf_s_until_the_designation_is_settled() -> None:
    """The pack designates blind (D-085): a wolf reads nobody's points but his own.

    What each of them weighed is laid out afterwards, by a fact of its own —
    which is what lets the spreads be blind without being secret for good.
    """
    other_wolf = Recipient(player=PlayerId("p9"), role=RoleName.WEREWOLF)
    spread = PriorityShared(actor=WOLF, allocations=(A_FEW_POINTS,))

    assert not spread.audience.reaches(other_wolf)
    assert PrioritiesRevealed(shares=(A_SPREAD,)).audience.reaches(other_wolf)


def test_inner_thoughts_belong_to_their_author_and_the_spectator() -> None:
    """The separation of thought and speech is held by the code (D-004, GL-3)."""
    for payload in (
        PrivateReasoningRecorded(player=WOLF, reasoning="Je vais accuser Camille."),
        NotebookEntryRecorded(player=WOLF, entry=0, note="Camille pivote vite."),
    ):
        assert payload.audience == Visibility.for_player(WOLF)


# --- The envelope ------------------------------------------------------------


def event(payload: EventPayload, *, sequence: int = 0) -> Event:
    return Event(
        sequence=sequence,
        recorded_at=WHEN,
        phase=Phase.DAY,
        day=2,
        payload=payload,
    )


def test_an_event_carries_when_and_where_it_happened() -> None:
    recorded = event(SpeechDelivered(speaker=WOLF, speech="Bonsoir."), sequence=7)

    assert recorded.sequence == 7
    assert recorded.recorded_at == WHEN
    assert recorded.phase is Phase.DAY
    assert recorded.day == 2


def test_an_event_takes_its_visibility_from_its_payload() -> None:
    """One source of truth: an envelope that could disagree would be believed."""
    recorded = event(RoleAssigned(player=WOLF, role=RoleName.WEREWOLF))

    assert recorded.visibility == Visibility.for_player(WOLF)
    assert recorded.is_visible_to(SPECTATOR)


def test_an_event_is_frozen() -> None:
    recorded = event(BallotAnnounced(voter=WOLF))

    with pytest.raises(ValidationError):
        recorded.sequence = 3


def test_an_event_survives_a_round_trip_through_json() -> None:
    """The journal is written as JSON lines, so this is the persistence contract."""
    recorded = event(SpeechDelivered(speaker=WOLF, speech="Théo, tu mens — j'en suis sûre."))

    assert Event.model_validate_json(recorded.model_dump_json()) == recorded


def test_the_serialised_form_states_the_audience() -> None:
    """Written out for the reader of a journal file, derived so it cannot lie."""
    dumped = event(RoleAssigned(player=WOLF, role=RoleName.WEREWOLF)).model_dump()

    assert dumped["visibility"] == Visibility.for_player(WOLF).model_dump()
