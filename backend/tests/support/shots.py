"""Hunters who owe a shot, and the states they owe it in."""

from lupus_ex_machina.engine.intents import RoleAction
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleActionName, RoleName
from lupus_ex_machina.engine.rules import GameRules, RoleOptions
from lupus_ex_machina.engine.state import GameState

HUNTER = PlayerId("p0")
WOLF = PlayerId("p1")
SEER = PlayerId("p2")
VILLAGER = PlayerId("p3")

TABLE = (
    Player(id=HUNTER, name="Adèle", seat=0, role=RoleName.HUNTER),
    Player(id=WOLF, name="Basile", seat=1, role=RoleName.WEREWOLF),
    Player(id=SEER, name="Camille", seat=2, role=RoleName.SEER),
    Player(id=VILLAGER, name="Diane", seat=3, role=RoleName.VILLAGER),
)

MANDATORY = GameRules()
OPTIONAL = GameRules(roles=RoleOptions(hunter_must_shoot=False))


def shot(target: PlayerId) -> RoleAction:
    return RoleAction(action=RoleActionName.SHOOT, target=target)


def dying_hunter() -> GameState:
    """The moment the hunter is dead and the shot is about to be fired."""
    return (
        GameState.initial(TABLE)
        .entering(Phase.DAY, day=2)
        .entering(Phase.RESOLUTION)
        .with_players_killed([HUNTER])
        .entering(Phase.AVENGING_SHOT)
    )
