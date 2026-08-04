"""Who gets to speak next (D-002).

This is the heart of the project. A language model wants nothing until it is
asked, so the engine asks: after every turn at the floor, each living player
answers how badly they want to speak, and the engine arbitrates.

The scores are what the arbitration is *made* of, so they are tested here on
their own, away from any game. What a real debate does with them is in
``test_runner.py``.
"""

import pytest
from pydantic import ValidationError

from lupus_ex_machina.engine.bidding import Bid, BidScore, DebateRules, elect, score_of
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.state import Speech

# --- What an agent answers when asked (J5.1.1) -------------------------------


def test_a_bid_carries_an_urgency_and_what_it_would_say() -> None:
    bid = Bid(urgency=70, intention="Réfuter l'accusation de Théo")

    assert bid.urgency == 70
    assert bid.intention == "Réfuter l'accusation de Théo"


@pytest.mark.parametrize("urgency", [-1, 101])
def test_an_urgency_outside_the_scale_is_refused(urgency: int) -> None:
    """0-100 is the scale the prompt states, so it is the scale the type holds."""
    with pytest.raises(ValidationError):
        Bid(urgency=urgency, intention="Parler")


@pytest.mark.parametrize("urgency", [0, 100])
def test_both_ends_of_the_scale_are_accepted(urgency: int) -> None:
    assert Bid(urgency=urgency, intention="Parler").urgency == urgency


def test_a_bid_says_what_it_is_for() -> None:
    """An empty intention is a bid nobody could arbitrate or stage (D-002)."""
    with pytest.raises(ValidationError):
        Bid(urgency=50, intention="")


# --- What a bid is worth once the day is taken into account (J5.1.2) ---------

RULES = DebateRules()

ADELE = PlayerId("p0")
BASILE = PlayerId("p1")
CAMILLE = PlayerId("p2")


def test_a_bid_in_an_untouched_day_is_worth_its_urgency() -> None:
    """Nothing has been said yet, so there is nothing to add or take away."""
    scored = score_of(
        Bid(urgency=60, intention="Ouvrir le débat"), bidder=ADELE, floor=(), rules=RULES
    )

    assert scored.total == 60
    assert scored.bidder is ADELE


def test_a_score_keeps_its_parts_apart() -> None:
    """The parts are what the spectator is shown.

    "Wanted it badly but had just spoken" and "did not much care" are two
    different stories, and one total cannot tell them apart.
    """
    scored = score_of(Bid(urgency=60, intention="Parler"), bidder=ADELE, floor=(), rules=RULES)

    assert (scored.urgency, scored.bonus, scored.penalty) == (60, 0, 0)


# --- Being talked to, and being accused (J5.1.3) -----------------------------


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


def test_being_spoken_to_makes_a_bid_more_pressing() -> None:
    scored = bid_of(BASILE, 50, (spoke(ADELE, addressed=BASILE),))

    assert scored.bonus == RULES.addressed_bonus
    assert scored.total == 50 + RULES.addressed_bonus


def test_being_accused_is_more_pressing_than_being_spoken_to() -> None:
    """An answer owed to the table weighs more than one owed to a person."""
    accused = bid_of(BASILE, 50, (spoke(ADELE, accused=BASILE),))
    addressed = bid_of(BASILE, 50, (spoke(ADELE, addressed=BASILE),))

    assert accused.bonus > addressed.bonus
    assert accused.bonus == RULES.accused_bonus


def test_being_both_spoken_to_and_accused_counts_twice() -> None:
    """Named to your face as the wolf: the two reasons to answer add up."""
    scored = bid_of(BASILE, 20, (spoke(ADELE, addressed=BASILE, accused=BASILE),))

    assert scored.bonus == RULES.addressed_bonus + RULES.accused_bonus


def test_nobody_else_is_made_more_pressing_by_it() -> None:
    scored = bid_of(CAMILLE, 50, (spoke(ADELE, addressed=BASILE, accused=BASILE),))

    assert scored.bonus == 0


def test_only_the_last_turn_calls_for_an_answer() -> None:
    """A bonus that outlived the exchange it came from would never fade."""
    floor = (spoke(ADELE, accused=BASILE), spoke(CAMILLE, addressed=ADELE))

    assert bid_of(BASILE, 50, floor).bonus == 0


# --- Having just spoken, and having spoken too much (J5.1.4) -----------------


def test_whoever_just_spoke_is_the_least_pressing() -> None:
    """The anti-monopoly of D-002: holding the floor is what costs the most."""
    scored = bid_of(ADELE, 80, (spoke(ADELE),))

    assert scored.penalty == RULES.recency_penalty


def test_the_cost_of_having_spoken_fades_turn_by_turn() -> None:
    """Decreasing, so a player is not shut out for the rest of the day."""
    costs = [
        bid_of(ADELE, 80, (spoke(ADELE), *(spoke(BASILE) for _ in range(since)))).penalty
        for since in range(RULES.recency_window)
    ]

    assert costs == sorted(costs, reverse=True), "each turn since must cost less"
    assert len(set(costs)) == len(costs), "and cost strictly less, or it does not fade"


def test_the_cost_of_having_spoken_runs_out() -> None:
    older = tuple(spoke(BASILE) for _ in range(RULES.recency_window))

    assert bid_of(ADELE, 80, (spoke(ADELE), *older)).penalty == 0


def test_a_player_who_has_not_spoken_owes_nothing() -> None:
    assert bid_of(CAMILLE, 50, (spoke(ADELE), spoke(BASILE))).penalty == 0


def test_talking_past_the_quota_of_the_day_costs() -> None:
    """The blunt end of the verbosity of models: a long day costs the floor."""
    long_winded = tuple(spoke(ADELE, words=RULES.word_quota) for _ in range(2))

    scored = bid_of(ADELE, 90, (*long_winded, *(spoke(BASILE) for _ in range(9))))

    assert scored.penalty == RULES.quota_penalty, "the recency has faded, the quota has not"


def test_the_quota_counts_only_what_this_player_said() -> None:
    others = tuple(spoke(BASILE, words=RULES.word_quota) for _ in range(3))

    assert bid_of(ADELE, 50, others).penalty == 0


def test_the_two_costs_add_up() -> None:
    """Just spoke, and spoke too much: both reasons to hear someone else."""
    scored = bid_of(ADELE, 90, (spoke(ADELE, words=RULES.word_quota + 1),))

    assert scored.penalty == RULES.recency_penalty + RULES.quota_penalty


# --- Nothing is decided in the code (J5.1.5) ---------------------------------

FLAT = DebateRules(
    addressed_bonus=0,
    accused_bonus=0,
    recency_penalty=0,
    recency_window=1,
    word_quota=0,
    quota_penalty=0,
)


def test_rules_that_weigh_nothing_leave_the_urgency_alone() -> None:
    """The proof that no coefficient is hidden in the code (D-002).

    Every circumstance that can move a score at once — just spoke, spoke far too
    much, was addressed and accused — against rules that price them all at zero.
    Anything left over would be a number the configuration cannot reach.
    """
    floor = (
        spoke(ADELE, words=10_000),
        spoke(BASILE, addressed=ADELE, accused=ADELE),
    )

    scored = score_of(Bid(urgency=42, intention="Répondre"), bidder=ADELE, floor=floor, rules=FLAT)

    assert (scored.bonus, scored.penalty) == (0, 0)
    assert scored.total == 42


def test_a_game_may_price_an_accusation_higher() -> None:
    fierce = DebateRules(accused_bonus=RULES.accused_bonus * 2)

    scored = score_of(
        Bid(urgency=10, intention="Me défendre"),
        bidder=BASILE,
        floor=(spoke(ADELE, accused=BASILE),),
        rules=fierce,
    )

    assert scored.bonus == fierce.accused_bonus


def test_a_game_may_let_the_floor_be_held() -> None:
    """Turning the anti-monopoly off is a setting, not a code change."""
    lenient = DebateRules(recency_penalty=0)

    scored = score_of(
        Bid(urgency=10, intention="Continuer"), bidder=ADELE, floor=(spoke(ADELE),), rules=lenient
    )

    assert scored.penalty == 0


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
