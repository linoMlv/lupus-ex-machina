"""How the pack settles on a prey, and what a tie costs it (D-008, D-050)."""

from lupus_ex_machina.engine.night import (
    designated_prey,
    resolve_night,
    tied_prey,
)
from support.nights import OTHER_WOLF, SEER, VILLAGER, WOLF, night, shared

# --- The pack settles on a prey (J4.3.4) -------------------------------------


def test_the_pack_takes_the_prey_its_points_agree_on() -> None:
    state = shared(shared(night(), WOLF, p5=70, p2=30), OTHER_WOLF, p5=50, p2=10)

    assert designated_prey(state) == VILLAGER


def test_one_wolf_can_pull_the_pack_away_from_a_prey() -> None:
    state = shared(shared(night(), WOLF, p5=50), OTHER_WOLF, p5=-60, p2=20)

    assert designated_prey(state) == SEER


# --- A tie, then a runoff, then nobody (J4.3.5) ------------------------------


def test_a_tie_leaves_the_prey_to_run_off_between() -> None:
    state = shared(night(), WOLF, p5=50, p2=50)

    assert set(tied_prey(state)) == {VILLAGER, SEER}


def test_a_settled_night_has_nothing_to_run_off() -> None:
    state = shared(night(), WOLF, p5=50, p2=20)

    assert tied_prey(state) == ()


def test_a_pack_that_wants_nobody_has_nothing_to_run_off() -> None:
    """There is no tie to break when no prey was ever wanted."""
    state = shared(night(), WOLF, p5=-10, p2=-20)

    assert tied_prey(state) == ()


def test_a_tie_that_survives_the_runoff_takes_nobody() -> None:
    """Second tie, no victim — the same rule as the day vote (D-050)."""
    state = shared(night(), WOLF, p5=50, p2=50)

    _, victims = resolve_night(state)

    assert victims == ()


def test_a_runoff_reopens_the_night_for_the_tied_prey_alone() -> None:
    """The second round is silent and restricted to the ex aequo (D-062)."""
    state = shared(night(), WOLF, p5=50, p2=50)

    reopened = state.reopened_for_runoff(tied_prey(state))

    assert reopened.priority_shares == ()
    assert set(reopened.runoff_targets) == {VILLAGER, SEER}


def test_a_reopened_night_settles_on_the_second_answer() -> None:
    state = shared(night(), WOLF, p5=50, p2=50)
    reopened = state.reopened_for_runoff(tied_prey(state))

    settled = shared(reopened, WOLF, p5=10)

    assert designated_prey(settled) == VILLAGER
