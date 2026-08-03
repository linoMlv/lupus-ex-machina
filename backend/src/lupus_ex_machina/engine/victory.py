"""End conditions (D-059).

The rule departs from the classic `wolves >= villagers` on purpose: at parity
the game continues, which leaves the village one more turn, *unless* only two
players remain. That single exception is what makes the "everybody dies" corner
case unreachable — the game is already over before the night that would produce
it.

The outcome is never cached in the state: it is a pure function of who is alive,
evaluated once per round, after the resolution is complete.
"""

from enum import StrEnum

from lupus_ex_machina.engine.roles import Team
from lupus_ex_machina.engine.state import GameState

PARITY_ENDGAME_SIZE = 2


class Outcome(StrEnum):
    """Which side won."""

    VILLAGE_WINS = "village_wins"
    WEREWOLVES_WIN = "werewolves_win"


def evaluate_victory(state: GameState) -> Outcome | None:
    """Return the winning side, or ``None`` while the game is still running."""
    wolves = len(state.living_of_team(Team.WEREWOLVES))
    if wolves == 0:
        return Outcome.VILLAGE_WINS

    villagers = len(state.living_of_team(Team.VILLAGE))
    if wolves > villagers:
        return Outcome.WEREWOLVES_WIN

    if wolves == villagers and wolves + villagers == PARITY_ENDGAME_SIZE:
        return Outcome.WEREWOLVES_WIN

    return None
