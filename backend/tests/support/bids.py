"""The seats a bid is scored for, and the day it is scored against."""

from lupus_ex_machina.engine.bidding import Bid, BidScore, score_of
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.records import Speech
from lupus_ex_machina.engine.rules import DebateOptions

RULES = DebateOptions()


ADELE = PlayerId("p0")


BASILE = PlayerId("p1")


CAMILLE = PlayerId("p2")


def spoke(
    speaker: PlayerId,
    *,
    words: int = 10,
    addressed: PlayerId | None = None,
    accused: PlayerId | None = None,
) -> Speech:
    """One turn at the floor, written the way a test reads it."""
    return Speech(speaker=speaker, words=words, addressed=addressed, accused=accused)


def bid_of(bidder: PlayerId, urgency: int, floor: tuple[Speech, ...]) -> BidScore:
    return score_of(
        Bid(urgency=urgency, intention="Répondre"), bidder=bidder, floor=floor, rules=RULES
    )
