"""The rules travel in the state, and the engine reads them (D-068)."""

from lupus_ex_machina.engine.intents import (
    PriorityPoint,
    RoleAction,
)
from lupus_ex_machina.engine.roles import RoleActionName
from lupus_ex_machina.engine.rules import (
    GameRules,
)
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import validate_intent
from lupus_ex_machina.engine.views import project
from support.configured_games import FORCED, TABLE, VILLAGER, WITCH, WOLF, night_of

# --- The rules travel in the state, and the engine reads them (D-068) --------


def test_a_game_carries_the_rules_it_is_played_by() -> None:
    """Handed to the state once, rather than to every function that reads them."""
    assert night_of(FORCED).rules == FORCED
    assert GameState.initial(TABLE).rules == GameRules()


def test_the_witch_is_shown_the_prey_the_lot_drew_for_the_pack() -> None:
    """The open point of J5, closed: the view reads the game's own rules.

    Under ``require_werewolf_target`` the prey is drawn rather than named
    (D-081). A view built from default rules shows the witch nothing, and she
    keeps a potion of life while the game kills someone she was never shown.
    """
    state = night_of(FORCED).with_prey_drawn(VILLAGER)

    assert project(state, WITCH).victim_tonight == VILLAGER


def test_the_validator_lets_the_witch_heal_the_prey_the_lot_drew() -> None:
    """And the validator reads them too, so it accepts what the view offered.

    The two must agree by construction. Reading the same field of the same state
    is what makes that true without a test having to watch over it.
    """
    state = night_of(FORCED).with_prey_drawn(VILLAGER)

    validate_intent(state, WITCH, RoleAction(action=RoleActionName.HEAL, target=VILLAGER))


def test_a_pack_that_names_its_prey_is_read_the_same_way_by_both() -> None:
    """The ordinary path, kept honest alongside the drawn one."""
    state = night_of(GameRules()).with_priority_share_from(
        WOLF, (PriorityPoint(target=VILLAGER, points=100),)
    )

    assert project(state, WITCH).victim_tonight == VILLAGER
    validate_intent(state, WITCH, RoleAction(action=RoleActionName.HEAL, target=VILLAGER))
