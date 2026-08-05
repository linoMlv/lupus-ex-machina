"""A game is played by the rules it was configured with, everywhere.

This is the property J5 closed without: ``_validate_healing`` asked the night
what the witch could see while handing it a *default* policy instead of the one
the game was set up with. The view made the same call, so the two agreed with
each other and disagreed with the game — the quietest kind of wrong.

The fix is structural rather than careful: the rules live in the state, so no
caller can supply the wrong ones or forget to supply any. That is the same
argument ``runoff_targets`` is in the state for — a view derived from the state
alone cannot be told about a restriction only the caller knew.
"""

from lupus_ex_machina.engine.intents import PriorityPoint, RoleAction
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleActionName, RoleName
from lupus_ex_machina.engine.rules import GameRules, NightOptions
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import validate_intent
from lupus_ex_machina.engine.views import project

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

FORCED = GameRules(night=NightOptions(require_werewolf_target=True))


def night_of(rules: GameRules) -> GameState:
    """A game played by those rules, on the night of its first day."""
    return (
        GameState.initial(TABLE, rules=rules)
        .entering(Phase.DAY, day=1)
        .entering(Phase.RESOLUTION)
        .entering(Phase.NIGHT)
    )


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
