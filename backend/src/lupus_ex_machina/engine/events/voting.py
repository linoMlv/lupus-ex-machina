"""Ballots: cast, announced, forced, and finally read out.

The clearest case of one act producing two facts, because the rules address two
audiences: *that* a player voted is public and closes the round (D-013, D-051),
*whom* they named is theirs alone until the count. Merging them would force the
filter to redact fields, which is precisely the design D-009 replaces.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from lupus_ex_machina.engine.events.fact import EventKind, Fact
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.visibility import Visibility


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


class VoteResolved(Fact):
    """The count is in. A tie eliminates nobody (D-050)."""

    kind: Literal[EventKind.VOTE_RESOLVED] = EventKind.VOTE_RESOLVED
    eliminated: PlayerId | None = None

    @property
    def audience(self) -> Visibility:
        """Public: death is never hidden (D-072)."""
        return Visibility.public()
