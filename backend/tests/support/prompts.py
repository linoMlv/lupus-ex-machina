"""Building the prompts a seat is handed, and the game they are built from."""

from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.llm.prompting import Briefing

SEER = PlayerId("p0")
WOLF = PlayerId("p1")
VILLAGER = PlayerId("p2")
OTHER = PlayerId("p3")

OTHER_WOLF = PlayerId("p4")

TABLE = (
    Player(id=SEER, name="Adèle", seat=0, role=RoleName.SEER),
    Player(id=WOLF, name="Basile", seat=1, role=RoleName.WEREWOLF),
    Player(id=VILLAGER, name="Camille", seat=2, role=RoleName.VILLAGER),
    Player(id=OTHER, name="Diane", seat=3, role=RoleName.HUNTER),
    Player(id=OTHER_WOLF, name="Émile", seat=4, role=RoleName.WEREWOLF),
)

A_PERSONALITY = "Tu es méthodique et tu détestes les conclusions hâtives."


def briefing() -> Briefing:
    return Briefing(personality=A_PERSONALITY)


def a_game(*, other_role: RoleName = RoleName.HUNTER) -> GameState:
    """The same table, with one player's role changed — a secret nobody else has."""
    table = tuple(
        player.model_copy(update={"role": other_role}) if player.id == OTHER else player
        for player in TABLE
    )
    return GameState.initial(table)
