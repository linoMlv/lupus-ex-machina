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

from lupus_ex_machina.engine.bidding import BidScore
from lupus_ex_machina.engine.intents import PriorityPoint
from lupus_ex_machina.engine.night import Revelation
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import RoleActionName, RoleName
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
    NIGHT_POWER_USED = "night_power_used"
    POWER_SPENT = "power_spent"
    SHOT_FIRED = "shot_fired"
    SEER_INSPECTED = "seer_inspected"
    SEER_FINDING_ANNOUNCED = "seer_finding_announced"
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
    FLOOR_AUCTIONED = "floor_auctioned"
    VOTE_FORCED = "vote_forced"
    BALLOTS_REVEALED = "ballots_revealed"
    FLOOR_CLAIMED = "floor_claimed"


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
    addressed: PlayerId | None = None
    accused: PlayerId | None = None

    @property
    def audience(self) -> Visibility:
        """Public: this is the shared transcript.

        Whom the speaker addressed and accused is public with it. They said it
        out loud — hiding the structure of a sentence everyone heard would be
        hiding nothing, and the auction that pays for it (D-002) has to be
        replayable from the journal.
        """
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


class NightPowerUsed(Fact):
    """A player used a single-target power on someone during the night.

    What they did, not what it came to: the effect is settled with the rest of
    the night (D-006), and what a seer learns is a fact of its own.
    """

    kind: Literal[EventKind.NIGHT_POWER_USED] = EventKind.NIGHT_POWER_USED
    actor: PlayerId
    action: RoleActionName
    target: PlayerId

    @property
    def audience(self) -> Visibility:
        """Its author: a power used in the dark is nobody else's business."""
        return Visibility.for_player(self.actor)


class ShotFired(Fact):
    """A hunter took someone along as he died (D-030).

    Public, and loudly so: the shot is fired by day and in front of everyone,
    which is half of what makes the role worth playing.
    """

    kind: Literal[EventKind.SHOT_FIRED] = EventKind.SHOT_FIRED
    hunter: PlayerId
    target: PlayerId
    chosen_by_the_hunter: bool
    """False when the hunter would not aim and the engine aimed for him (D-055)."""

    @property
    def audience(self) -> Visibility:
        """Public."""
        return Visibility.public()


class PowerSpent(Fact):
    """A power that works once has now been used up (D-029).

    Recorded on its own because it outlives the round: the choice that spent it
    is wiped when the night closes, and a game rebuilt from the journal would
    otherwise hand the potion back.
    """

    kind: Literal[EventKind.POWER_SPENT] = EventKind.POWER_SPENT
    actor: PlayerId
    action: RoleActionName

    @property
    def audience(self) -> Visibility:
        """Its holder: the table never learns what is left in the cupboard."""
        return Visibility.for_player(self.actor)


class SeerInspected(Fact):
    """What the seer read on the player she looked at (D-031)."""

    kind: Literal[EventKind.SEER_INSPECTED] = EventKind.SEER_INSPECTED
    seer: PlayerId
    target: PlayerId
    revelation: Revelation

    @property
    def audience(self) -> Visibility:
        """Hers alone, and the spectator's."""
        return Visibility.for_player(self.seer)


class SeerFindingAnnounced(Fact):
    """The table is told what the seer found, never on whom (D-031).

    A fact of its own rather than the private one with a wider audience: the
    name of the player she looked at must not travel with it, and the only way
    to be sure of that is for it not to be there.
    """

    kind: Literal[EventKind.SEER_FINDING_ANNOUNCED] = EventKind.SEER_FINDING_ANNOUNCED
    revelation: Revelation

    @property
    def audience(self) -> Visibility:
        """Public, which is the whole point of the option."""
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


class ForcedVoteReason(StrEnum):
    """Why a debate was put to the vote rather than ending on its own (D-013)."""

    DEBATE_EXHAUSTED = "debate_exhausted"
    """An auction produced neither a word nor a ballot: nobody had anything left
    to say, and another round of bidding would only spend model calls (D-060)."""

    TURN_BUDGET_SPENT = "turn_budget_spent"
    """The day ran out of turns. A ceiling, not a rule of the game."""

    MODERATOR = "moderator"
    """The user cut the debate short (D-048)."""


class RevealedBallot(BaseModel):
    """One ballot as the count shows it: who voted, and whom they named."""

    model_config = ConfigDict(frozen=True)

    voter: PlayerId
    target: PlayerId | None = None


class BallotsRevealed(Fact):
    """The count, laid out for the table (D-013, D-051).

    Produced only when the configuration says so, which is the shape every
    information option takes: the option decides whether the fact exists, never
    who may read it (D-009).

    All at once, and that is the point. Revealing ballots one by one would let
    the table follow a herd; revealed together, they are also the moment the
    staging is built on — every head turning to its target at the same instant
    (D-075).
    """

    kind: Literal[EventKind.BALLOTS_REVEALED] = EventKind.BALLOTS_REVEALED
    ballots: tuple[RevealedBallot, ...] = ()

    @property
    def audience(self) -> Visibility:
        """Public: this is the count, read out to the table."""
        return Visibility.public()


class VoteForced(Fact):
    """The debate was closed for the table rather than by it.

    Recorded, and public: a round that ends because the moderator said so, or
    because nobody had anything left to say, did not end the way D-013 means a
    round to end, and a spectator reading the journal should be able to tell.
    """

    kind: Literal[EventKind.VOTE_FORCED] = EventKind.VOTE_FORCED
    reason: ForcedVoteReason

    @property
    def audience(self) -> Visibility:
        """Public: everyone at the table is about to be made to vote."""
        return Visibility.public()


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
    """The night is over. It may take nobody, or more than one (D-029)."""

    kind: Literal[EventKind.NIGHT_RESOLVED] = EventKind.NIGHT_RESOLVED
    victims: tuple[PlayerId, ...] = ()

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


class FloorAuctioned(Fact):
    """One round of bidding for the floor, winner and losers alike (D-002).

    Kept whole, and kept for the spectator. What a player wanted to say and how
    badly they wanted to say it is not something the table is entitled to — but
    it is what the losers of an auction are staged reacting to (D-075), and the
    only material there will ever be for calibrating the coefficients.
    """

    kind: Literal[EventKind.FLOOR_AUCTIONED] = EventKind.FLOOR_AUCTIONED
    scores: tuple[BidScore, ...] = ()
    winner: PlayerId | None = None

    @property
    def audience(self) -> Visibility:
        """The spectator alone: an unspoken intention stays unspoken."""
        return Visibility.spectator_only()


class FloorClaimed(Fact):
    """The human player took the floor with their button rather than by bidding.

    Public: the table sees somebody speak out of turn, which is exactly what the
    button does. Hiding it would make the debate look like it arbitrated
    something it never arbitrated.
    """

    kind: Literal[EventKind.FLOOR_CLAIMED] = EventKind.FLOOR_CLAIMED
    player: PlayerId

    @property
    def audience(self) -> Visibility:
        """Public: interrupting is not a secret."""
        return Visibility.public()


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
    | NightPowerUsed
    | PowerSpent
    | ShotFired
    | SeerInspected
    | SeerFindingAnnounced
    | PriorityShared
    | PackSpeechDelivered
    | RunoffOpened
    | VoteResolved
    | NightResolved
    | RoleRevealed
    | GameEnded
    | IntentRejected
    | PrivateReasoningRecorded
    | NotebookEntryRecorded
    | FloorAuctioned
    | VoteForced
    | BallotsRevealed
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
