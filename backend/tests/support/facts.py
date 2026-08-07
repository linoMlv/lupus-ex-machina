"""The catalogue of facts, read as a whole."""

from datetime import UTC, datetime
from typing import get_args

from lupus_ex_machina.engine.bidding import BidScore
from lupus_ex_machina.engine.events import (
    BallotAnnounced,
    BallotCast,
    BallotsRevealed,
    EventPayload,
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
from lupus_ex_machina.engine.visibility import Visibility

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
