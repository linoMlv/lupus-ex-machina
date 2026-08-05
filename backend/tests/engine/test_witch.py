"""The witch (D-029, D-054).

She wakes after the pack, sees whom it took, and may spend one of two potions —
one to save that victim, one to kill someone else. Each potion works once in a
game, and she may use only one of them per night.

Seeing the victim is why she is woken last: a witch called before the pack would
have nothing to look at. That ordering is a rule of the night, not an accident of
the loop.
"""

import pytest

from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.intents import PriorityPoint, RoleAction
from lupus_ex_machina.engine.night import night_callers, resolve_night, victim_seen_by_the_witch
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleActionName, RoleName
from lupus_ex_machina.engine.rules import GameRules, RoleOptions
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import validate_intent

WOLF = PlayerId("p0")
WITCH = PlayerId("p1")
SEER = PlayerId("p2")
VILLAGER = PlayerId("p3")
OTHER_VILLAGER = PlayerId("p4")

TABLE = (
    Player(id=WOLF, name="Adèle", seat=0, role=RoleName.WEREWOLF),
    Player(id=WITCH, name="Basile", seat=1, role=RoleName.WITCH),
    Player(id=SEER, name="Camille", seat=2, role=RoleName.SEER),
    Player(id=VILLAGER, name="Diane", seat=3, role=RoleName.VILLAGER),
    Player(id=OTHER_VILLAGER, name="Émile", seat=4, role=RoleName.VILLAGER),
)

ASLEEP_WITHOUT_POTIONS = GameRules(roles=RoleOptions(wake_witch_without_potions=False))


def night(rules: GameRules | None = None) -> GameState:
    return (
        GameState.initial(TABLE, rules=rules)
        .entering(Phase.DAY, day=1)
        .entering(Phase.RESOLUTION)
        .entering(Phase.NIGHT)
    )


def taken(target: PlayerId, state: GameState | None = None) -> GameState:
    """A night where the pack has designated that prey."""
    return (state or night()).with_priority_share_from(
        WOLF, (PriorityPoint(target=target, points=100),)
    )


def heal(target: PlayerId) -> RoleAction:
    return RoleAction(action=RoleActionName.HEAL, target=target)


def poison(target: PlayerId) -> RoleAction:
    return RoleAction(action=RoleActionName.POISON, target=target)


# --- She sees whom the pack took (J4.5.1) ------------------------------------


def test_the_witch_is_woken_after_the_pack() -> None:
    """Otherwise she would have nothing to look at (D-029)."""
    called = [player.id for player in night_callers(night())]

    assert called.index(WITCH) > called.index(WOLF)


def test_she_sees_the_prey_the_pack_settled_on() -> None:
    assert victim_seen_by_the_witch(taken(VILLAGER)) == VILLAGER


def test_she_sees_nobody_when_the_pack_took_nobody() -> None:
    assert victim_seen_by_the_witch(night()) is None


def test_she_sees_herself_when_the_pack_came_for_her() -> None:
    assert victim_seen_by_the_witch(taken(WITCH)) == WITCH


# --- The potion of life (J4.5.2, J4.5.3) -------------------------------------


def test_she_may_save_the_victim_of_the_night() -> None:
    validate_intent(taken(VILLAGER), WITCH, heal(VILLAGER))


def test_she_may_save_herself() -> None:
    """Explicitly allowed (D-029), and the only way she survives a night."""
    validate_intent(taken(WITCH), WITCH, heal(WITCH))


def test_she_may_not_save_someone_the_pack_did_not_take() -> None:
    """The potion answers the night's attack; there is nothing else to answer."""
    with pytest.raises(IllegalIntentError, match="victim"):
        validate_intent(taken(VILLAGER), WITCH, heal(OTHER_VILLAGER))


def test_she_may_not_save_anyone_on_a_night_without_a_victim() -> None:
    with pytest.raises(IllegalIntentError, match="victim"):
        validate_intent(night(), WITCH, heal(VILLAGER))


def test_a_saved_victim_lives_through_the_night() -> None:
    state = taken(VILLAGER).with_night_choice_from(WITCH, RoleActionName.HEAL, VILLAGER)

    resolved, victims = resolve_night(state)

    assert victims == ()
    assert resolved.is_alive(VILLAGER)


# --- The potion of death (J4.5.2) --------------------------------------------


def test_she_may_poison_another_living_player() -> None:
    validate_intent(night(), WITCH, poison(VILLAGER))


def test_she_may_not_poison_herself() -> None:
    with pytest.raises(IllegalIntentError, match="themselves"):
        validate_intent(night(), WITCH, poison(WITCH))


def test_she_may_not_poison_the_dead() -> None:
    state = night().with_players_killed([VILLAGER])

    with pytest.raises(IllegalIntentError, match="dead"):
        validate_intent(state, WITCH, poison(VILLAGER))


def test_a_poisoned_player_dies_with_the_night() -> None:
    state = night().with_night_choice_from(WITCH, RoleActionName.POISON, VILLAGER)

    resolved, victims = resolve_night(state)

    assert set(victims) == {VILLAGER}
    assert not resolved.is_alive(VILLAGER)


def test_the_pack_and_the_poison_can_take_two_in_one_night() -> None:
    state = taken(VILLAGER).with_night_choice_from(WITCH, RoleActionName.POISON, OTHER_VILLAGER)

    resolved, victims = resolve_night(state)

    assert set(victims) == {VILLAGER, OTHER_VILLAGER}
    assert len(resolved.living) == len(TABLE) - 2


# --- One potion a night, one use each (J4.5.2) -------------------------------


def test_she_uses_at_most_one_potion_a_night() -> None:
    state = taken(VILLAGER).with_night_choice_from(WITCH, RoleActionName.HEAL, VILLAGER)

    with pytest.raises(IllegalIntentError, match="already"):
        validate_intent(state, WITCH, poison(OTHER_VILLAGER))


def test_a_potion_already_drunk_is_gone_for_good() -> None:
    state = taken(VILLAGER).with_power_spent_by(WITCH, RoleActionName.HEAL)

    with pytest.raises(IllegalIntentError, match=r"no .* left"):
        validate_intent(state, WITCH, heal(VILLAGER))


def test_spending_one_potion_leaves_the_other() -> None:
    state = night().with_power_spent_by(WITCH, RoleActionName.HEAL)

    validate_intent(state, WITCH, poison(VILLAGER))


def test_a_spent_potion_survives_the_end_of_a_round() -> None:
    """Potions are spent for the game, not for the night (D-029)."""
    state = night().with_power_spent_by(WITCH, RoleActionName.POISON)

    assert state.cleared_of_round_choices().has_spent(WITCH, RoleActionName.POISON)


def test_using_a_potion_spends_it() -> None:
    state = taken(VILLAGER).with_night_choice_from(WITCH, RoleActionName.HEAL, VILLAGER)

    resolved, _ = resolve_night(state)

    assert resolved.has_spent(WITCH, RoleActionName.HEAL)
    assert not resolved.has_spent(WITCH, RoleActionName.POISON)


# --- Being woken with nothing to pour (J4.5.4, D-054) ------------------------


def test_by_default_she_is_woken_even_with_no_potions_left() -> None:
    assert RoleOptions().wake_witch_without_potions is True


def test_an_empty_handed_witch_is_still_called_by_default() -> None:
    state = (
        night()
        .with_power_spent_by(WITCH, RoleActionName.HEAL)
        .with_power_spent_by(WITCH, RoleActionName.POISON)
    )

    assert WITCH in {player.id for player in night_callers(state)}


def test_an_empty_handed_witch_sleeps_through_when_the_setting_says_so() -> None:
    state = (
        night(ASLEEP_WITHOUT_POTIONS)
        .with_power_spent_by(WITCH, RoleActionName.HEAL)
        .with_power_spent_by(WITCH, RoleActionName.POISON)
    )

    called = {player.id for player in night_callers(state)}

    assert WITCH not in called
    assert WOLF in called, "the rest of the night is untouched"


def test_a_witch_with_one_potion_left_is_always_called() -> None:
    state = night(ASLEEP_WITHOUT_POTIONS).with_power_spent_by(WITCH, RoleActionName.HEAL)

    assert WITCH in {player.id for player in night_callers(state)}
