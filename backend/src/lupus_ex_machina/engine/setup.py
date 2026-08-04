"""Building the initial state of a game.

Dealing is a shuffle, not an assembly: the composition already says which roles
sit at the table (D-056, D-061), so this module only hands them out and draws the
names.

A game opens either from a table size, which takes the default composition, or
from a composition itself. One entry point, and nothing to keep in agreement
between a count and the roles that go with it.
"""

from lupus_ex_machina.engine.composition import Composition, default_composition
from lupus_ex_machina.engine.names import FIRST_NAMES
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.rng import Rng
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.state import GameState


def create_game(table: int | Composition, *, rng: Rng) -> GameState:
    """Deal roles and names, and return the state Night 0 starts from."""
    composition = default_composition(table) if isinstance(table, int) else table

    roles = _deal_roles(composition, rng)
    names = _deal_names(composition.size, rng)

    players = tuple(
        Player(id=PlayerId(f"player-{seat}"), name=name, seat=seat, role=role)
        for seat, (name, role) in enumerate(zip(names, roles, strict=True))
    )
    return GameState.initial(players)


def _deal_roles(composition: Composition, rng: Rng) -> list[RoleName]:
    roles = list(composition.roles)
    rng.shuffle(roles)
    return roles


def _deal_names(player_count: int, rng: Rng) -> list[str]:
    """Draw distinct names, without replacement (D-042, D-057)."""
    return rng.sample(FIRST_NAMES, player_count)
