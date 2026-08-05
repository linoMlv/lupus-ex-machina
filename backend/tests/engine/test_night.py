"""The night: who is woken, in what order, and what it all adds up to.

Nothing takes effect while the night runs (D-006). Powers are collected as they
are played and resolved together at the end, because the alternative — applying
each as it comes — is what makes the witch incoherent: she must see a victim who
has been *designated*, not one who is already dead.

The pack designates by weight rather than by name (D-008), and a tie spares
everyone after a silent runoff (D-050, D-062).
"""

import pytest

from lupus_ex_machina.engine.intents import PriorityPoint
from lupus_ex_machina.engine.night import (
    designated_prey,
    night_callers,
    prey_drawn_by_lot,
    resolve_night,
    tied_prey,
    victim_seen_by_the_witch,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.rules import GameRules, NightOptions
from lupus_ex_machina.engine.state import GameState

WOLF = PlayerId("p0")
OTHER_WOLF = PlayerId("p1")
SEER = PlayerId("p2")
WITCH = PlayerId("p3")
HUNTER = PlayerId("p4")
VILLAGER = PlayerId("p5")

TABLE = (
    Player(id=WOLF, name="Adèle", seat=0, role=RoleName.WEREWOLF),
    Player(id=OTHER_WOLF, name="Basile", seat=1, role=RoleName.WEREWOLF),
    Player(id=SEER, name="Camille", seat=2, role=RoleName.SEER),
    Player(id=WITCH, name="Diane", seat=3, role=RoleName.WITCH),
    Player(id=HUNTER, name="Émile", seat=4, role=RoleName.HUNTER),
    Player(id=VILLAGER, name="Faustine", seat=5, role=RoleName.VILLAGER),
)


def night(state: GameState | None = None, *, rules: GameRules | None = None) -> GameState:
    base = state or GameState.initial(TABLE, rules=rules)
    return base.entering(Phase.DAY, day=1).entering(Phase.RESOLUTION).entering(Phase.NIGHT)


def forced_night(state: GameState | None = None) -> GameState:
    """A night the pack may not leave empty-handed (D-078)."""
    return night(state, rules=FORCED)


def shared(state: GameState, actor: PlayerId, **points: int) -> GameState:
    """Record one wolf's spread, written as ``shared(state, WOLF, p5=60)``."""
    return state.with_priority_share_from(
        actor,
        tuple(
            PriorityPoint(target=PlayerId(target), points=amount)
            for target, amount in points.items()
        ),
    )


FORCED = GameRules(night=NightOptions(require_werewolf_target=True))


# --- Who is woken, and when (J4.2.1) -----------------------------------------


def test_the_night_calls_the_seer_then_the_pack_then_the_witch() -> None:
    """The order is a rule: the witch must see a victim the pack has designated.

    Those who hold a power come first, in that order. Everyone else has a turn
    too (D-084) — see ``test_night_turn.py`` — but their place in the queue is a
    sweep by seat rather than a ranking.
    """
    called = [player.role for player in night_callers(night())][:4]

    assert called == [
        RoleName.SEER,
        RoleName.WEREWOLF,
        RoleName.WEREWOLF,
        RoleName.WITCH,
    ]


def test_the_roles_with_no_power_come_after_the_ones_that_have_one() -> None:
    """The hunter fires by day and in public, even when the night killed them (D-030)."""
    called = [player.role for player in night_callers(night())]

    assert called[4:] == [RoleName.HUNTER, RoleName.VILLAGER]


def test_the_night_never_wakes_the_dead() -> None:
    state = night().with_players_killed([SEER])

    assert SEER not in {player.id for player in night_callers(state)}


def test_wolves_are_woken_in_seat_order_within_their_turn() -> None:
    """A stable order, so a game replays the same way twice."""
    wolves = [player.id for player in night_callers(night()) if player.role is RoleName.WEREWOLF]

    assert wolves == [WOLF, OTHER_WOLF]


# --- Nothing happens before the end of the night (J4.2.2, J4.2.3) ------------


def test_recording_a_share_kills_nobody() -> None:
    """The whole reason the night is resolved in one go (D-006)."""
    state = shared(forced_night(), WOLF, p5=100)

    assert state.is_alive(VILLAGER)
    assert len(state.living) == len(TABLE)


def test_the_victim_only_dies_when_the_night_is_resolved() -> None:
    state = shared(shared(night(), WOLF, p5=60), OTHER_WOLF, p5=40)

    resolved, victims = resolve_night(state)

    assert victims == (VILLAGER,)
    assert not resolved.is_alive(VILLAGER)


def test_resolving_a_night_clears_what_it_collected() -> None:
    state = shared(night(), WOLF, p5=100)

    resolved, _ = resolve_night(state)

    assert resolved.priority_shares == ()
    assert resolved.runoff_targets == ()


def test_a_night_nobody_acted_in_takes_nobody() -> None:
    resolved, victims = resolve_night(night())

    assert victims == ()
    assert len(resolved.living) == len(TABLE)


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
