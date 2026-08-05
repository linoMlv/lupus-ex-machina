"""Arbitrating who speaks next (D-002).

The problem this module exists for: a language model does not *want* anything
until it is asked. Turn-taking round the table would make that invisible, so
the engine asks instead. After every turn at the floor, each living player
answers how badly they want to speak, and the engine scores the answers.

Two things are had for free. Silence becomes an act — a player with nothing to
say bids low and stays quiet, which the others can read. And nobody can hold
the floor, because having just spoken is what costs the most in the next
auction.

Field names are English because they are code; what an agent fills in is French,
because it is content shown on screen or sent to a model (HR-6).
"""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import Rng
from lupus_ex_machina.engine.rules import DebateOptions
from lupus_ex_machina.engine.state import Speech


class Bid(BaseModel):
    """What one player answers when asked whether they want the floor."""

    model_config = ConfigDict(frozen=True)

    urgency: int = Field(
        ge=0,
        le=100,
        description="À quel point tu veux prendre la parole maintenant, de 0 à 100.",
    )
    intention: str = Field(
        min_length=1,
        description="En quelques mots, ce que tu dirais si on te donnait la parole.",
    )


class BidScore(BaseModel):
    """One bid, and what the arbitration made of it.

    The parts are kept apart rather than summed on the spot. This is what the
    spectator is shown: "wanted it badly but had just spoken" and "did not much
    care" are two different stories that one total cannot tell apart.
    """

    model_config = ConfigDict(frozen=True)

    bidder: PlayerId
    urgency: int
    bonus: int = 0
    penalty: int = 0

    @property
    def total(self) -> int:
        """What the bid is worth once the day so far is taken into account."""
        return self.urgency + self.bonus - self.penalty


class Auction(BaseModel):
    """One round of bidding, and whom it handed the floor to.

    Every bid is kept, not just the winning one. The losers are what the
    spectator is shown reacting (D-075) and what the coefficients will be
    calibrated against: thrown away here, the protocol would have to be
    reopened to get them back.
    """

    model_config = ConfigDict(frozen=True)

    scores: tuple[BidScore, ...] = ()
    """Every bid weighed, most pressing first."""

    winner: PlayerId | None = None
    """Who speaks next, or nobody when the auction was empty."""


def elect(
    bids: Mapping[PlayerId, Bid],
    *,
    floor: tuple[Speech, ...],
    rules: DebateOptions,
    rng: Rng,
) -> Auction:
    """Weigh every bid and hand the floor to the most pressing one.

    A tie is drawn rather than settled by seat or by the order the bids came
    in, for the reason D-081 settled the pack's own tie by lot: any fixed order
    would quietly favour the same players in every game.
    """
    scored = sorted(
        (score_of(bid, bidder=bidder, floor=floor, rules=rules) for bidder, bid in bids.items()),
        key=lambda score: -score.total,
    )
    if not scored:
        return Auction()

    pressing = [score for score in scored if bids[score.bidder].urgency >= rules.minimum_urgency]
    if not pressing:
        # Everyone bid, nobody bid hard enough: the floor stays empty, which the
        # debate reads as having run out of things to say (D-060). The bids are
        # kept all the same — what was offered is what the coefficients are
        # calibrated against.
        return Auction(scores=tuple(scored))

    best = pressing[0].total
    tied = [score.bidder for score in pressing if score.total == best]
    return Auction(scores=tuple(scored), winner=rng.choice(tied))


def score_of(
    bid: Bid, *, bidder: PlayerId, floor: tuple[Speech, ...], rules: DebateOptions
) -> BidScore:
    """Weigh one bid against the turns the day has already had."""
    return BidScore(
        bidder=bidder,
        urgency=bid.urgency,
        bonus=_owed_an_answer(bidder, floor, rules),
        penalty=_just_spoke(bidder, floor, rules) + _spoke_too_much(bidder, floor, rules),
    )


def _owed_an_answer(bidder: PlayerId, floor: tuple[Speech, ...], rules: DebateOptions) -> int:
    """What the last turn at the floor left this player owing the table.

    Only the last one counts. A bonus that outlived the exchange that earned it
    would never fade, and the debate would keep answering a question two turns
    old.
    """
    if not floor:
        return 0

    last = floor[-1]
    addressed = rules.addressed_bonus if last.addressed == bidder else 0
    accused = rules.accused_bonus if last.accused == bidder else 0
    return addressed + accused


def _just_spoke(bidder: PlayerId, floor: tuple[Speech, ...], rules: DebateOptions) -> int:
    """What this player still owes for having held the floor recently.

    Full price for the turn just taken, then fading with every turn somebody
    else takes. Fading rather than binary: a player who spoke a moment ago
    should be hard to beat, not shut out of the rest of the day.
    """
    turns_since = _turns_since_speaking(bidder, floor)
    if turns_since is None or turns_since >= rules.recency_window:
        return 0

    return rules.recency_penalty * (rules.recency_window - turns_since) // rules.recency_window


def _turns_since_speaking(bidder: PlayerId, floor: tuple[Speech, ...]) -> int | None:
    """How many turns have been taken since this player last spoke.

    Zero when the last turn was theirs; ``None`` when they have not spoken.
    """
    for turns_since, speech in enumerate(reversed(floor)):
        if speech.speaker == bidder:
            return turns_since
    return None


def _spoke_too_much(bidder: PlayerId, floor: tuple[Speech, ...], rules: DebateOptions) -> int:
    """What this player owes for the room they have already taken up today."""
    spent = sum(speech.words for speech in floor if speech.speaker == bidder)
    return rules.quota_penalty if spent > rules.word_quota else 0
