"""How the pack designates its prey, and what a spread may hold (D-008)."""

import pytest

from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.intents import (
    PriorityPoint,
    SharePriority,
)
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.validation import validate_intent
from support.validation_games import DEVOUR_VILLAGER, VILLAGER, WOLF, day, night

# --- The pack designates its prey (D-008) ------------------------------------


def spread(**points: int) -> SharePriority:
    """A wolf's spread, written as ``spread(p2=60, p3=-10)``."""
    return SharePriority(
        allocations=tuple(
            PriorityPoint(target=PlayerId(target), points=amount)
            for target, amount in points.items()
        )
    )


def test_a_legal_spread_passes() -> None:
    validate_intent(night(), WOLF, spread(p2=60, p3=40))


def test_a_spread_of_negative_points_passes() -> None:
    """Pushing a prey away is a legal use of the budget (D-008)."""
    validate_intent(night(), WOLF, spread(p2=60, p3=-40))


def test_spending_less_than_the_budget_passes() -> None:
    """The budget is a ceiling, not a quota: under-spending costs influence, nothing else."""
    validate_intent(night(), WOLF, spread(p2=10))


def test_a_spread_over_the_budget_is_refused() -> None:
    with pytest.raises(IllegalIntentError, match="at most"):
        validate_intent(night(), WOLF, spread(p2=80, p3=40))


def test_negative_points_count_against_the_budget() -> None:
    """Otherwise a wolf could weigh every prey at full strength for free."""
    with pytest.raises(IllegalIntentError, match="at most"):
        validate_intent(night(), WOLF, spread(p2=80, p3=-40))


def test_naming_the_same_prey_twice_is_refused() -> None:
    duplicated = SharePriority(
        allocations=(
            PriorityPoint(target=VILLAGER, points=30),
            PriorityPoint(target=VILLAGER, points=30),
        )
    )

    with pytest.raises(IllegalIntentError, match="twice"):
        validate_intent(night(), WOLF, duplicated)


def test_only_a_wolf_may_weigh_the_prey() -> None:
    with pytest.raises(IllegalIntentError, match="villager cannot devour"):
        validate_intent(night(), VILLAGER, spread(p2=10))


def test_the_pack_may_not_weigh_one_of_its_own() -> None:
    with pytest.raises(IllegalIntentError, match="not prey"):
        validate_intent(night(), WOLF, spread(p1=50))


def test_the_pack_may_not_weigh_a_dead_player() -> None:
    state = night().with_players_killed([VILLAGER])

    with pytest.raises(IllegalIntentError, match="dead"):
        validate_intent(state, WOLF, spread(p2=50))


def test_a_wolf_spreads_its_points_only_once_a_night() -> None:
    state = night().with_priority_share_from(WOLF, (PriorityPoint(target=VILLAGER, points=50),))

    with pytest.raises(IllegalIntentError, match="already spread"):
        validate_intent(state, WOLF, spread(p3=50))


def test_a_runoff_narrows_the_prey_the_pack_may_weigh() -> None:
    """The second round is restricted to the ex aequo (D-062)."""
    state = night().reopened_for_runoff((VILLAGER,))

    validate_intent(state, WOLF, spread(p2=50))
    with pytest.raises(IllegalIntentError, match="not prey"):
        validate_intent(state, WOLF, spread(p3=50))


def test_the_pack_only_designates_at_night() -> None:
    with pytest.raises(IllegalIntentError, match="at night"):
        validate_intent(day(), WOLF, spread(p2=50))


def test_a_role_action_never_stands_in_for_the_pack_vote() -> None:
    """One wolf naming one prey is not how the pack decides (D-008)."""
    with pytest.raises(IllegalIntentError, match="spreading points"):
        validate_intent(night(), WOLF, DEVOUR_VILLAGER)
