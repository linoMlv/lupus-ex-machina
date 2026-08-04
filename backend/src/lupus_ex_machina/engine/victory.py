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


def decide(*, werewolves: int, villagers: int) -> Outcome | None:
    """Return the winning side for a table of that shape, or ``None`` if it plays on.

    Kept apart from the state so the rule has a single home: the end of a game
    and the acceptance of a starting composition (D-061) are the same question
    asked at two moments, and two copies of it would drift.
    """
    if werewolves == 0:
        return Outcome.VILLAGE_WINS

    if werewolves > villagers:
        return Outcome.WEREWOLVES_WIN

    if werewolves == villagers and werewolves + villagers == PARITY_ENDGAME_SIZE:
        return Outcome.WEREWOLVES_WIN

    return None


def evaluate_victory(state: GameState) -> Outcome | None:
    """Return the winning side, or ``None`` while the game is still running."""
    return decide(
        werewolves=len(state.living_of_team(Team.WEREWOLVES)),
        villagers=len(state.living_of_team(Team.VILLAGE)),
    )
