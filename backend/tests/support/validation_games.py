"""Tables the validation tests judge intents against: one game, and two phases."""

from lupus_ex_machina.engine.intents import (
    RoleAction,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleActionName, RoleName
from lupus_ex_machina.engine.state import GameState

WOLF = PlayerId("p0")
OTHER_WOLF = PlayerId("p1")
VILLAGER = PlayerId("p2")
OTHER_VILLAGER = PlayerId("p3")
UNKNOWN = PlayerId("nobody")

DEVOUR_VILLAGER = RoleAction(action=RoleActionName.DEVOUR, target=VILLAGER)


def game() -> GameState:
    return GameState.initial(
        (
            Player(id=WOLF, name="Alice", seat=0, role=RoleName.WEREWOLF),
            Player(id=OTHER_WOLF, name="Bruno", seat=1, role=RoleName.WEREWOLF),
            Player(id=VILLAGER, name="Camille", seat=2, role=RoleName.VILLAGER),
            Player(id=OTHER_VILLAGER, name="Dounia", seat=3, role=RoleName.VILLAGER),
        )
    )


def day(state: GameState | None = None, *, number: int = 2) -> GameState:
    """Move a game to a plain debate day — day 2 has no bootstrap restriction."""
    return (state or game()).entering(Phase.DAY, day=number)


def night(state: GameState | None = None) -> GameState:
    return day(state).entering(Phase.RESOLUTION).entering(Phase.NIGHT)
