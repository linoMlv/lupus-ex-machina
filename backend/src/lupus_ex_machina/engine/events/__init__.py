"""The facts a game is made of, and the envelope that records them.

The facts themselves are grouped by the moment of the game they belong to —
:mod:`opening`, :mod:`debate`, :mod:`voting`, :mod:`night`, :mod:`thinking`,
:mod:`dying` — over the single rule of :mod:`fact`: every fact declares its own
audience (D-009).

The union stays here, in one piece. It is what the journal validates against and
what the audience catalogue of the tests is derived from, so splitting it would
be splitting the one list that has to be exhaustive.

Field names are English because they are code; the values agents fill in are
French, because they are shown on screen and read by the models (HR-6).
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field

from lupus_ex_machina.engine.events.debate import (
    FloorAuctioned,
    FloorClaimed,
    SpeechDelivered,
)
from lupus_ex_machina.engine.events.dying import GameEnded, RoleRevealed, ShotFired
from lupus_ex_machina.engine.events.fact import EventKind, Fact
from lupus_ex_machina.engine.events.night import (
    NightPowerUsed,
    NightResolved,
    PackRunoffOpened,
    PowerSpent,
    PrioritiesRevealed,
    PriorityShared,
    RevealedShare,
    SeerFindingAnnounced,
    SeerInspected,
)
from lupus_ex_machina.engine.events.opening import (
    PackRevealed,
    PhaseEntered,
    PlayerSeated,
    RoleAssigned,
)
from lupus_ex_machina.engine.events.thinking import (
    IntentRejected,
    NotebookEntryDropped,
    NotebookEntryRecorded,
    PrivateReasoningRecorded,
)
from lupus_ex_machina.engine.events.voting import (
    BallotAnnounced,
    BallotCast,
    BallotsRevealed,
    ForcedVoteReason,
    RevealedBallot,
    RunoffOpened,
    VoteForced,
    VoteResolved,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.visibility import Recipient, Visibility

EventPayload = Annotated[
    PlayerSeated
    | RoleAssigned
    | PackRevealed
    | PhaseEntered
    | SpeechDelivered
    | BallotCast
    | BallotAnnounced
    | NightPowerUsed
    | PowerSpent
    | ShotFired
    | SeerInspected
    | SeerFindingAnnounced
    | PriorityShared
    | RunoffOpened
    | PackRunoffOpened
    | VoteResolved
    | NightResolved
    | RoleRevealed
    | GameEnded
    | IntentRejected
    | PrivateReasoningRecorded
    | NotebookEntryRecorded
    | NotebookEntryDropped
    | FloorAuctioned
    | VoteForced
    | BallotsRevealed
    | PrioritiesRevealed
    | FloorClaimed,
    Field(discriminator="kind"),
]


class Event(BaseModel):
    """A fact, placed in the game it belongs to."""

    model_config = ConfigDict(frozen=True)

    sequence: int = Field(ge=0, description="Rank in the journal, and the order of replay.")
    recorded_at: datetime
    phase: Phase
    day: int = Field(ge=0)
    payload: EventPayload

    # mypy does not model decorators stacked on a property; the pair is the way
    # pydantic exposes a derived field, and it is checked by the tests instead.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def visibility(self) -> Visibility:
        """Who may know this event.

        Derived rather than stored: an envelope holding its own copy could end
        up disagreeing with the fact it wraps, and a reader would believe the
        envelope.
        """
        return self.payload.audience

    def is_visible_to(self, recipient: Recipient) -> bool:
        """Whether that recipient is entitled to this event."""
        return self.visibility.reaches(recipient)


__all__ = [
    "BallotAnnounced",
    "BallotCast",
    "BallotsRevealed",
    "Event",
    "EventKind",
    "EventPayload",
    "Fact",
    "FloorAuctioned",
    "FloorClaimed",
    "ForcedVoteReason",
    "GameEnded",
    "IntentRejected",
    "NightPowerUsed",
    "NightResolved",
    "NotebookEntryDropped",
    "NotebookEntryRecorded",
    "PackRevealed",
    "PackRunoffOpened",
    "PhaseEntered",
    "PlayerSeated",
    "PowerSpent",
    "PrioritiesRevealed",
    "PriorityShared",
    "PrivateReasoningRecorded",
    "RevealedBallot",
    "RevealedShare",
    "RoleAssigned",
    "RoleRevealed",
    "RunoffOpened",
    "SeerFindingAnnounced",
    "SeerInspected",
    "ShotFired",
    "SpeechDelivered",
    "VoteForced",
    "VoteResolved",
]
