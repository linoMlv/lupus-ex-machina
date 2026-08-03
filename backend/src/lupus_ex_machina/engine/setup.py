"""Building the initial state of a game.

Six to eight players, eight being the hard maximum of V1 (D-056). The number of
wolves comes from a table rather than a ratio: the project owner set those
values, and a ratio would silently drift from them.

The powered roles (seer, witch, hunter) join the composition in J4. Until then
every non-wolf is a villager, which is enough to exercise the whole loop.
"""

from lupus_ex_machina.engine.errors import EngineError
from lupus_ex_machina.engine.names import FIRST_NAMES
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.rng import Rng
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.state import GameState

WEREWOLVES_BY_PLAYER_COUNT: dict[int, int] = {6: 1, 7: 2, 8: 2}

MINIMUM_PLAYERS = min(WEREWOLVES_BY_PLAYER_COUNT)
MAXIMUM_PLAYERS = max(WEREWOLVES_BY_PLAYER_COUNT)


class UnsupportedPlayerCountError(EngineError):
    """A player count V1 does not support."""


def create_game(player_count: int, *, rng: Rng) -> GameState:
    """Deal roles and names, and return the state Night 0 starts from."""
    werewolves = _werewolves_for(player_count)
    roles = _deal_roles(player_count, werewolves, rng)
    names = _deal_names(player_count, rng)

    players = tuple(
        Player(id=PlayerId(f"player-{seat}"), name=name, seat=seat, role=role)
        for seat, (name, role) in enumerate(zip(names, roles, strict=True))
    )
    return GameState.initial(players)


def _werewolves_for(player_count: int) -> int:
    try:
        return WEREWOLVES_BY_PLAYER_COUNT[player_count]
    except KeyError as unsupported:
        raise UnsupportedPlayerCountError(
            f"V1 supports {MINIMUM_PLAYERS} to {MAXIMUM_PLAYERS} players, not {player_count}"
        ) from unsupported


def _deal_roles(player_count: int, werewolves: int, rng: Rng) -> list[RoleName]:
    roles = [RoleName.WEREWOLF] * werewolves
    roles += [RoleName.VILLAGER] * (player_count - werewolves)
    rng.shuffle(roles)
    return roles


def _deal_names(player_count: int, rng: Rng) -> list[str]:
    """Draw distinct names, without replacement (D-042, D-057)."""
    return rng.sample(FIRST_NAMES, player_count)
