"""Who takes the floor once every bid is in (J5.1.6, D-002)."""

from lupus_ex_machina.engine.bidding import Bid, elect
from lupus_ex_machina.engine.rng import create_rng
from support.bids import ADELE, BASILE, CAMILLE, RULES, bid_of, spoke

# --- Who takes the floor (J5.1.6) --------------------------------------------


def wants(urgency: int) -> Bid:
    return Bid(urgency=urgency, intention="Parler")


def test_the_most_pressing_bid_takes_the_floor() -> None:
    auction = elect(
        {ADELE: wants(30), BASILE: wants(80), CAMILLE: wants(50)},
        floor=(),
        rules=RULES,
        rng=create_rng(1),
    )

    assert auction.winner == BASILE


def test_a_bid_is_weighed_before_it_is_compared() -> None:
    """Urgency alone would hand the floor to whoever just held it."""
    auction = elect(
        {ADELE: wants(80), BASILE: wants(60)},
        floor=(spoke(ADELE),),
        rules=RULES,
        rng=create_rng(1),
    )

    assert auction.winner == BASILE


def test_an_auction_keeps_every_bid_it_weighed() -> None:
    """Losing bids are the raw material of the staging (D-075) and of tuning."""
    auction = elect(
        {ADELE: wants(30), BASILE: wants(80), CAMILLE: wants(50)},
        floor=(),
        rules=RULES,
        rng=create_rng(1),
    )

    assert [score.bidder for score in auction.scores] == [BASILE, CAMILLE, ADELE]


def test_an_auction_nobody_entered_gives_the_floor_to_nobody() -> None:
    auction = elect({}, floor=(), rules=RULES, rng=create_rng(1))

    assert auction.winner is None
    assert auction.scores == ()


def test_a_tie_is_drawn_rather_than_given_to_a_seat() -> None:
    """Same reasoning as D-081: a fixed order would favour the same player."""
    tied = {ADELE: wants(50), BASILE: wants(50), CAMILLE: wants(50)}

    winners = {
        elect(tied, floor=(), rules=RULES, rng=create_rng(seed)).winner for seed in range(20)
    }

    assert winners == {ADELE, BASILE, CAMILLE}


def test_the_same_seed_hands_the_floor_to_the_same_player() -> None:
    tied = {ADELE: wants(50), BASILE: wants(50)}

    drawn = {elect(tied, floor=(), rules=RULES, rng=create_rng(3)).winner for _ in range(5)}

    assert len(drawn) == 1


def test_a_tie_is_only_drawn_between_the_bids_that_tied() -> None:
    bids = {ADELE: wants(50), BASILE: wants(50), CAMILLE: wants(10)}

    winners = {
        elect(bids, floor=(), rules=RULES, rng=create_rng(seed)).winner for seed in range(20)
    }

    assert winners == {ADELE, BASILE}


def test_spending_the_whole_quota_is_still_within_it() -> None:
    """Where exactly the line falls.

    The quota is what a player may spend, not the point at which spending
    starts to cost. Nothing pins that down but a test: a mutation moving the
    comparison by one went unnoticed until this was written.
    """
    exactly = (spoke(ADELE, words=RULES.word_quota),)

    assert bid_of(ADELE, 50, (*exactly, *(spoke(BASILE) for _ in range(9)))).penalty == 0
