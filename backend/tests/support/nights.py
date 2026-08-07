"""Nights to wake, and the tables that play them."""

from lupus_ex_machina.engine.intents import PriorityPoint
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
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
