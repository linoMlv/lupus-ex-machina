"""Building the initial state of a game.

Dealing is a shuffle, not an assembly: the composition already says which roles
sit at the table (D-056, D-061), so this module only hands them out and draws the
names.

A game is opened from its rules and from nothing else (D-068). The table size,
the composition and the seed are all read from the same record the game will
then carry, so there is no way to deal one game and play another.
"""

from lupus_ex_machina.engine.composition import Composition, default_composition
from lupus_ex_machina.engine.names import FIRST_NAMES
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.rng import Rng, create_rng
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.rules import GameRules, TableOptions
from lupus_ex_machina.engine.state import GameState


def create_game(rules: GameRules | None = None, *, rng: Rng | None = None) -> GameState:
    """Deal roles and names, and return the state Night 0 starts from.

    Without a generator, one is dealt from the seed of the rules: a game is
    reproducible by configuration alone (D-040). Callers that keep their own —
    the console command shares one with its agents — pass it in.
    """
    settled = rules if rules is not None else GameRules()
    drawing = rng if rng is not None else create_rng(settled.table.seed)

    composition = dealt_composition(settled.table)
    roles = _deal_roles(composition, drawing)
    names = _deal_names(composition.size, drawing)

    players = tuple(
        Player(id=PlayerId(f"player-{seat}"), name=name, seat=seat, role=role)
        for seat, (name, role) in enumerate(zip(names, roles, strict=True))
    )
    return GameState.initial(players, rules=settled)


def dealt_composition(table: TableOptions) -> Composition:
    """The composition that table is dealt from: its own, or its preset (D-061)."""
    if table.composition is not None:
        return table.composition
    return default_composition(table.player_count)


def _deal_roles(composition: Composition, rng: Rng) -> list[RoleName]:
    roles = list(composition.roles)
    rng.shuffle(roles)
    return roles


def _deal_names(player_count: int, rng: Rng) -> list[str]:
    """Draw distinct names, without replacement (D-042, D-057)."""
    return rng.sample(FIRST_NAMES, player_count)
