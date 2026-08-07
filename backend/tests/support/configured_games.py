"""Games dealt under one option or another, to see what the engine does with it."""

from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.rules import (
    GameRules,
    NightOptions,
)
from lupus_ex_machina.engine.state import GameState

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
