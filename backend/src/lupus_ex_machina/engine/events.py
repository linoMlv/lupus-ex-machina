"""The facts a game is made of, and the envelope that records them.

Every fact declares the audience it is addressed to, and it declares it *itself*
rather than at the place it is recorded: a caller cannot forget, and cannot get
it wrong twice in two different ways. :class:`Fact` is abstract on that single
property, so a type that says nothing about who may know it cannot even be
built (D-009).

One act of the game sometimes produces two facts, because the rules address two
audiences. Casting a named ballot is the clearest case: *that* a player voted is
public and closes the round (D-013, D-051), *whom* they named is theirs alone
until the count. Two audiences, therefore two facts — merging them would force
the filter to redact fields, which is precisely the design D-009 replaces.

Field names are English because they are code; the values agents fill in are
French, because they are shown on screen and read by the models (HR-6).
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from lupus_ex_machina.engine.intents import PriorityPoint
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.victory import Outcome
from lupus_ex_machina.engine.visibility import Recipient, Visibility


class EventKind(StrEnum):
    """Discriminator of the fact union."""

    PLAYER_SEATED = "player_seated"
    ROLE_ASSIGNED = "role_assigned"
    PACK_REVEALED = "pack_revealed"
    PHASE_ENTERED = "phase_entered"
    SPEECH_DELIVERED = "speech_delivered"
    BALLOT_CAST = "ballot_cast"
    BALLOT_ANNOUNCED = "ballot_announced"
    PRIORITY_SHARED = "priority_shared"
    PACK_SPEECH_DELIVERED = "pack_speech_delivered"
    RUNOFF_OPENED = "runoff_opened"
    VOTE_RESOLVED = "vote_resolved"
    NIGHT_RESOLVED = "night_resolved"
    ROLE_REVEALED = "role_revealed"
    INTENT_REJECTED = "intent_rejected"
    GAME_ENDED = "game_ended"
    PRIVATE_REASONING_RECORDED = "private_reasoning_recorded"
    NOTEBOOK_ENTRY_RECORDED = "notebook_entry_recorded"


class Fact(BaseModel, ABC):
    """Something that happened, and the audience entitled to know it.

    Declaring an audience is what makes a fact recordable: the property is
    abstract so the guarantee is structural rather than a convention to
    remember.
    """

    model_config = ConfigDict(frozen=True)

    @property
    @abstractmethod
    def audience(self) -> Visibility:
        """Who may know this."""


# --- Setting the table -------------------------------------------------------


class PlayerSeated(Fact):
    """A player takes their seat. Identities and seats are public from the start."""

    kind: Literal[EventKind.PLAYER_SEATED] = EventKind.PLAYER_SEATED
    player: PlayerId
    name: str
    seat: int = Field(ge=0)

    @property
    def audience(self) -> Visibility:
        """Public: everyone sees who sits where."""
        return Visibility.public()


class RoleAssigned(Fact):
    """A player is dealt their role — the one secret the whole game turns on."""

    kind: Literal[EventKind.ROLE_ASSIGNED] = EventKind.ROLE_ASSIGNED
    player: PlayerId
    role: RoleName

    @property
    def audience(self) -> Visibility:
        """That player alone."""
        return Visibility.for_player(self.player)


class PackRevealed(Fact):
    """The wolves meet on Night 0, without speaking (D-032)."""

    kind: Literal[EventKind.PACK_REVEALED] = EventKind.PACK_REVEALED
    members: tuple[PlayerId, ...]

    @property
    def audience(self) -> Visibility:
        """The pack, and nobody else at the table."""
        return Visibility.for_role(RoleName.WEREWOLF)


# --- The course of the game --------------------------------------------------


class PhaseEntered(Fact):
    """The game moves to another phase."""

    kind: Literal[EventKind.PHASE_ENTERED] = EventKind.PHASE_ENTERED
    phase: Phase
    day: int = Field(ge=0)

    @property
    def audience(self) -> Visibility:
        """Public: the rhythm of the game is shared by everyone."""
        return Visibility.public()


class SpeechDelivered(Fact):
    """Someone takes the floor. The only thing a player says that others hear (D-004)."""

    kind: Literal[EventKind.SPEECH_DELIVERED] = EventKind.SPEECH_DELIVERED
    speaker: PlayerId
    speech: str = Field(min_length=1)

    @property
    def audience(self) -> Visibility:
        """Public: this is the shared transcript."""
        return Visibility.public()


class BallotCast(Fact):
    """A vote, with whom it names. A missing target is a blank vote (D-027)."""

    kind: Literal[EventKind.BALLOT_CAST] = EventKind.BALLOT_CAST
    voter: PlayerId
    target: PlayerId | None = None

    @property
    def audience(self) -> Visibility:
        """Public when blank, otherwise the voter's own.

        A blank vote is public the moment it is cast — it costs the floor *and*
        reveals the choice (D-027). A named one stays with its author, which is
        also what lets an agent re-read its own vote while the table cannot.
        """
        if self.target is None:
            return Visibility.public()
        return Visibility.for_player(self.voter)


class BallotAnnounced(Fact):
    """That a player has voted, never for whom (D-013, D-051)."""

    kind: Literal[EventKind.BALLOT_ANNOUNCED] = EventKind.BALLOT_ANNOUNCED
    voter: PlayerId

    @property
    def audience(self) -> Visibility:
        """Public: the pressure of the end of a round rests on it."""
        return Visibility.public()


class PriorityShared(Fact):
    """A wolf spreads its points over the prey, on the pack's channel (D-008)."""

    kind: Literal[EventKind.PRIORITY_SHARED] = EventKind.PRIORITY_SHARED
    actor: PlayerId
    allocations: tuple[PriorityPoint, ...]

    @property
    def audience(self) -> Visibility:
        """The pack."""
        return Visibility.for_role(RoleName.WEREWOLF)


class PackSpeechDelivered(Fact):
    """Something said on the private channel of the pack (D-007).

    A fact of its own rather than a flag on public speech: the two have two
    audiences, and one type carrying both would put the filter in charge of
    redacting a field.
    """

    kind: Literal[EventKind.PACK_SPEECH_DELIVERED] = EventKind.PACK_SPEECH_DELIVERED
    speaker: PlayerId
    speech: str = Field(min_length=1)

    @property
    def audience(self) -> Visibility:
        """The pack, and never the table."""
        return Visibility.for_role(RoleName.WEREWOLF)


class RunoffOpened(Fact):
    """The pack tied, so a silent second round is held between the ex aequo (D-062)."""

    kind: Literal[EventKind.RUNOFF_OPENED] = EventKind.RUNOFF_OPENED
    targets: tuple[PlayerId, ...]

    @property
    def audience(self) -> Visibility:
        """The pack: the tie happened on its own channel."""
        return Visibility.for_role(RoleName.WEREWOLF)


# --- Resolutions -------------------------------------------------------------


class VoteResolved(Fact):
    """The count is in. A tie eliminates nobody (D-050)."""

    kind: Literal[EventKind.VOTE_RESOLVED] = EventKind.VOTE_RESOLVED
    eliminated: PlayerId | None = None

    @property
    def audience(self) -> Visibility:
        """Public: death is never hidden (D-072)."""
        return Visibility.public()


class NightResolved(Fact):
    """The night is over, with or without a victim."""

    kind: Literal[EventKind.NIGHT_RESOLVED] = EventKind.NIGHT_RESOLVED
    victim: PlayerId | None = None

    @property
    def audience(self) -> Visibility:
        """Public: death is never hidden (D-072)."""
        return Visibility.public()


class RoleRevealed(Fact):
    """The role of a player who just died, when the configuration allows it (D-072)."""

    kind: Literal[EventKind.ROLE_REVEALED] = EventKind.ROLE_REVEALED
    player: PlayerId
    role: RoleName

    @property
    def audience(self) -> Visibility:
        """Public — the option decides whether the fact happens at all, not who sees it."""
        return Visibility.public()


class GameEnded(Fact):
    """A side has won (D-059)."""

    kind: Literal[EventKind.GAME_ENDED] = EventKind.GAME_ENDED
    outcome: Outcome

    @property
    def audience(self) -> Visibility:
        """Public."""
        return Visibility.public()


# --- What only the audience sees ---------------------------------------------


class IntentRejected(Fact):
    """An agent asked for something the rules refuse.

    Kept because it is the raw material for judging how models behave (J7): a
    game where every second intent is refused is a prompt problem, and nothing
    else would show it.
    """

    kind: Literal[EventKind.INTENT_REJECTED] = EventKind.INTENT_REJECTED
    actor: PlayerId
    reason: str

    @property
    def audience(self) -> Visibility:
        """The spectator alone: the table never learns that someone fumbled."""
        return Visibility.spectator_only()


class PrivateReasoningRecorded(Fact):
    """What a player thought before acting, which nobody at the table hears (D-004).

    The engine has no thoughts to record until the models arrive (J7). The fact
    exists now because the guarantee it carries belongs to the information
    model, not to the agents: thought never crosses into speech, and that is
    held by the code rather than by a prompt (GL-3).
    """

    kind: Literal[EventKind.PRIVATE_REASONING_RECORDED] = EventKind.PRIVATE_REASONING_RECORDED
    player: PlayerId
    reasoning: str

    @property
    def audience(self) -> Visibility:
        """Its author, and the spectator watching over their shoulder."""
        return Visibility.for_player(self.player)


class NotebookEntryRecorded(Fact):
    """A line a player wrote in their own notebook (D-005).

    Like private reasoning, filled in by J7; the audience is settled here.
    """

    kind: Literal[EventKind.NOTEBOOK_ENTRY_RECORDED] = EventKind.NOTEBOOK_ENTRY_RECORDED
    player: PlayerId
    note: str

    @property
    def audience(self) -> Visibility:
        """Its author, and the spectator."""
        return Visibility.for_player(self.player)


EventPayload = Annotated[
    PlayerSeated
    | RoleAssigned
    | PackRevealed
    | PhaseEntered
    | SpeechDelivered
    | BallotCast
    | BallotAnnounced
    | PriorityShared
    | PackSpeechDelivered
    | RunoffOpened
    | VoteResolved
    | NightResolved
    | RoleRevealed
    | GameEnded
    | IntentRejected
    | PrivateReasoningRecorded
    | NotebookEntryRecorded,
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
