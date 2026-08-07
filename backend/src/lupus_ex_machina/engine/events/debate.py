"""The floor: who won it, who claimed it, and what was said from it.

Speech is the only thing a player produces that others hear (D-004). The auction
that decided who speaks is kept too, but for the spectator alone — an unspoken
intention stays unspoken.
"""

from typing import Literal

from pydantic import Field

from lupus_ex_machina.engine.bidding import BidScore
from lupus_ex_machina.engine.events.fact import EventKind, Fact
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.visibility import Visibility


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
