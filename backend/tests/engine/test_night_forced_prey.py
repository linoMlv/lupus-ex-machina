"""A pack made to designate someone, and the lot that settles it (D-078, D-081)."""

import pytest

from lupus_ex_machina.engine.night import (
    designated_prey,
    prey_drawn_by_lot,
    victim_seen_by_the_witch,
)
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameRules, NightOptions
from support.nights import (
    FORCED,
    HUNTER,
    OTHER_WOLF,
    SEER,
    VILLAGER,
    WITCH,
    WOLF,
    forced_night,
    night,
    shared,
)

# --- The pack may be made to designate someone (J4.3.6, D-078) ---------------


def test_by_default_the_pack_may_leave_the_night_empty() -> None:
    assert NightOptions().require_werewolf_target is False


def test_forcing_the_pack_changes_nothing_when_it_had_already_settled() -> None:
    state = shared(forced_night(), WOLF, p5=70, p2=30)

    assert designated_prey(state) == VILLAGER


@pytest.mark.parametrize("rules", [GameRules(), FORCED])
def test_the_pack_never_takes_one_of_its_own(rules: GameRules) -> None:
    """Its own are not prey, so the points spent on them buy nothing."""
    state = shared(night(rules=rules), WOLF, p0=90, p1=90)

    assert designated_prey(state) is None


# --- What the lot does for a pack that must designate someone (D-081) --------


def test_a_pack_that_settled_is_never_sent_to_the_lot() -> None:
    """The lot answers a pack that did not choose, never one that did."""
    state = shared(forced_night(), WOLF, p5=70, p2=30)

    assert prey_drawn_by_lot(state, rng=create_rng(1)) is None


def test_a_pack_free_to_take_nobody_is_never_sent_to_the_lot() -> None:
    """An ordinary night: the pack tied, and a tie simply spares everyone."""
    state = shared(night(), WOLF, p5=50, p2=50)

    assert prey_drawn_by_lot(state, rng=create_rng(1)) is None


def test_the_lot_takes_one_of_the_prey_the_pack_was_torn_between() -> None:
    state = shared(forced_night(), WOLF, p5=50, p2=50)

    assert prey_drawn_by_lot(state, rng=create_rng(1)) in {VILLAGER, SEER}


def test_the_lot_falls_on_any_prey_when_the_pack_named_nobody() -> None:
    """Nothing to break a tie between, so every living prey is in the draw."""
    drawn = prey_drawn_by_lot(forced_night(), rng=create_rng(1))

    assert drawn is not None
    assert drawn not in {WOLF, OTHER_WOLF}, "never one of its own"


def test_the_lot_never_takes_a_dead_player() -> None:
    state = forced_night().with_players_killed([SEER, VILLAGER])

    assert prey_drawn_by_lot(state, rng=create_rng(1)) in {WITCH, HUNTER}


def test_the_lot_does_not_always_fall_on_the_same_prey() -> None:
    """The point of D-081: the seat no longer decides, so nobody is safe by rank."""
    state = shared(forced_night(), WOLF, p5=50, p2=50)

    drawn = {prey_drawn_by_lot(state, rng=create_rng(seed)) for seed in range(20)}

    assert drawn == {VILLAGER, SEER}


def test_the_same_seed_draws_the_same_prey() -> None:
    """Reproducible, so a surprising game can be replayed exactly (D-040)."""
    state = shared(forced_night(), WOLF, p5=50, p2=50)

    assert len({prey_drawn_by_lot(state, rng=create_rng(7)) for _ in range(5)}) == 1


def test_a_pack_with_no_prey_left_draws_nobody() -> None:
    """Defensive: such a night cannot start, since the game would already be over.

    The victory is evaluated at the end of every round (D-059), so a round never
    opens with the village wiped out. The guard is here because the alternative
    to returning nothing is raising out of a pure resolution.
    """
    state = forced_night().with_players_killed([SEER, WITCH, HUNTER, VILLAGER])

    assert prey_drawn_by_lot(state, rng=create_rng(1)) is None


def test_the_prey_drawn_is_the_one_the_night_takes() -> None:
    state = shared(forced_night(), WOLF, p5=50, p2=50).with_prey_drawn(SEER)

    assert designated_prey(state) == SEER


def test_a_drawn_prey_is_wiped_with_the_rest_of_the_round() -> None:
    state = shared(night(), WOLF, p5=50, p2=50).with_prey_drawn(SEER)

    assert state.cleared_of_round_choices().drawn_prey is None


def test_a_night_designates_the_same_prey_however_often_it_is_asked() -> None:
    """Why the draw is held once and kept, rather than redrawn on every reading.

    The witch is shown the prey (D-029) and the resolution takes it. Two
    readings of one night that disagreed would have her heal someone other than
    the player who dies.
    """
    state = shared(forced_night(), WOLF, p5=50, p2=50).with_prey_drawn(SEER)

    assert len({designated_prey(state) for _ in range(5)}) == 1
    assert victim_seen_by_the_witch(state) == designated_prey(state)
