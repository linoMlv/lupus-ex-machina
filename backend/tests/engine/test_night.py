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
from lupus_ex_machina.engine.night import designated_prey, night_callers, resolve_night, tied_prey
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.policy import InformationPolicy
from lupus_ex_machina.engine.roles import RoleName
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


def night(state: GameState | None = None) -> GameState:
    base = state or GameState.initial(TABLE)
    return base.entering(Phase.DAY, day=1).entering(Phase.RESOLUTION).entering(Phase.NIGHT)


def shared(state: GameState, actor: PlayerId, **points: int) -> GameState:
    """Record one wolf's spread, written as ``shared(state, WOLF, p5=60)``."""
    return state.with_priority_share_from(
        actor,
        tuple(
            PriorityPoint(target=PlayerId(target), points=amount)
            for target, amount in points.items()
        ),
    )


DISCREET = InformationPolicy()
FORCED = InformationPolicy(require_werewolf_target=True)


# --- Who is woken, and when (J4.2.1) -----------------------------------------


def test_the_night_wakes_the_seer_then_the_pack_then_the_witch() -> None:
    """The order is a rule: the witch must see a victim the pack has designated."""
    called = [state.role for state in night_callers(night())]

    assert called == [
        RoleName.SEER,
        RoleName.WEREWOLF,
        RoleName.WEREWOLF,
        RoleName.WITCH,
    ]


def test_the_night_never_wakes_a_role_with_nothing_to_do() -> None:
    """The hunter fires by day and in public, even when the night killed them (D-030)."""
    woken = {player.role for player in night_callers(night())}

    assert RoleName.VILLAGER not in woken
    assert RoleName.HUNTER not in woken


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
    state = shared(night(), WOLF, p5=100)

    assert state.is_alive(VILLAGER)
    assert len(state.living) == len(TABLE)


def test_the_victim_only_dies_when_the_night_is_resolved() -> None:
    state = shared(shared(night(), WOLF, p5=60), OTHER_WOLF, p5=40)

    resolved, victims = resolve_night(state, policy=DISCREET)

    assert victims == (VILLAGER,)
    assert not resolved.is_alive(VILLAGER)


def test_resolving_a_night_clears_what_it_collected() -> None:
    state = shared(night(), WOLF, p5=100)

    resolved, _ = resolve_night(state, policy=DISCREET)

    assert resolved.priority_shares == ()
    assert resolved.runoff_targets == ()


def test_a_night_nobody_acted_in_takes_nobody() -> None:
    resolved, victims = resolve_night(night(), policy=DISCREET)

    assert victims == ()
    assert len(resolved.living) == len(TABLE)


# --- The pack settles on a prey (J4.3.4) -------------------------------------


def test_the_pack_takes_the_prey_its_points_agree_on() -> None:
    state = shared(shared(night(), WOLF, p5=70, p2=30), OTHER_WOLF, p5=50, p2=10)

    assert designated_prey(state, policy=DISCREET) == VILLAGER


def test_one_wolf_can_pull_the_pack_away_from_a_prey() -> None:
    state = shared(shared(night(), WOLF, p5=50), OTHER_WOLF, p5=-60, p2=20)

    assert designated_prey(state, policy=DISCREET) == SEER


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

    _, victims = resolve_night(state, policy=DISCREET)

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

    assert designated_prey(settled, policy=DISCREET) == VILLAGER


# --- The pack may be made to designate someone (J4.3.6, D-078) ---------------


def test_by_default_the_pack_may_leave_the_night_empty() -> None:
    assert InformationPolicy().require_werewolf_target is False


def test_a_forced_pack_still_takes_someone_after_a_tie() -> None:
    state = shared(night(), WOLF, p5=50, p2=50)

    assert designated_prey(state, policy=FORCED) is not None


def test_a_forced_pack_takes_one_of_the_prey_it_was_torn_between() -> None:
    state = shared(night(), WOLF, p5=50, p2=50)

    assert designated_prey(state, policy=FORCED) in {VILLAGER, SEER}


def test_a_forced_pack_that_named_nobody_still_takes_someone() -> None:
    """Nothing to break a tie between, so the choice falls on the living prey."""
    taken = designated_prey(night(), policy=FORCED)

    assert taken is not None
    assert taken not in {WOLF, OTHER_WOLF}, "never one of its own"


def test_forcing_the_pack_changes_nothing_when_it_had_already_settled() -> None:
    state = shared(night(), WOLF, p5=70, p2=30)

    assert designated_prey(state, policy=FORCED) == VILLAGER


def test_a_forced_choice_is_the_same_on_every_run() -> None:
    """Deterministic, so a game replays identically (D-040)."""
    state = shared(night(), WOLF, p5=50, p2=50)

    assert len({designated_prey(state, policy=FORCED) for _ in range(5)}) == 1


def test_a_forced_pack_never_takes_a_dead_player() -> None:
    state = night().with_players_killed([SEER, VILLAGER])

    taken = designated_prey(state, policy=FORCED)

    assert taken in {WITCH, HUNTER}


@pytest.mark.parametrize("policy", [DISCREET, FORCED])
def test_the_pack_never_takes_one_of_its_own(policy: InformationPolicy) -> None:
    taken = designated_prey(night(), policy=policy)

    assert taken not in {WOLF, OTHER_WOLF}


def test_a_forced_pack_with_no_prey_left_takes_nobody() -> None:
    """Defensive: such a night cannot start, since the game would already be over.

    The victory is evaluated at the end of every round (D-059), so a round never
    opens with the village wiped out. The guard is here because the alternative
    to returning nothing is raising out of a pure resolution.
    """
    state = night().with_players_killed([SEER, WITCH, HUNTER, VILLAGER])

    assert designated_prey(state, policy=FORCED) is None
