"""Who sits at the table.

A composition is the multiset of roles a game is dealt from — one entry per seat.
Modelling it as the actual list of roles rather than as counts per role keeps it
honest: there is nothing to reconcile between a total and its parts, and dealing
is a shuffle rather than an assembly.

The default tables are the ones the project owner wrote out (D-056), pinned value
by value. A ratio would have been shorter and would have drifted from them the
day the table grows.

Anyone may deal their own table (D-061). The only thing asked of it is that the
game it describes has not already been won, and that question is put to the
victory rule itself rather than to a copy of it.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from lupus_ex_machina.engine.errors import EngineError
from lupus_ex_machina.engine.roles import RoleName, Team, team_of
from lupus_ex_machina.engine.victory import decide


class UnsupportedPlayerCountError(EngineError):
    """A table size V1 does not deal."""


# Six to eight players, eight being the hard maximum of V1 (D-056). Stated ahead
# of the default tables because a composition is validated against them as it is
# built, the default ones included; a test holds the two in agreement.
MINIMUM_PLAYERS = 6
MAXIMUM_PLAYERS = 8


class Composition(BaseModel):
    """The roles a game is dealt from, one per seat."""

    model_config = ConfigDict(frozen=True)

    roles: tuple[RoleName, ...]

    @property
    def size(self) -> int:
        """How many players sit at this table."""
        return len(self.roles)

    def count(self, role: RoleName) -> int:
        """How many seats hold that role."""
        return sum(1 for dealt in self.roles if dealt is role)

    def count_of_team(self, team: Team) -> int:
        """How many seats belong to that side."""
        return sum(1 for dealt in self.roles if team_of(dealt) is team)

    @model_validator(mode="after")
    def _seats_a_playable_table(self) -> Self:
        """Refuse a table V1 does not deal, or a game that is over before it starts."""
        if not MINIMUM_PLAYERS <= self.size <= MAXIMUM_PLAYERS:
            raise ValueError(
                f"A table seats {MINIMUM_PLAYERS} to {MAXIMUM_PLAYERS} players, not {self.size}"
            )

        settled = decide(
            werewolves=self.count_of_team(Team.WEREWOLVES),
            villagers=self.count_of_team(Team.VILLAGE),
        )
        if settled is not None:
            raise ValueError(f"This composition describes a game that is already over: {settled}")
        return self


def _table(*, werewolves: int, villagers: int) -> tuple[RoleName, ...]:
    """One of each powered role, plus the wolves and the plain villagers (D-056)."""
    return (
        (RoleName.WEREWOLF,) * werewolves
        + (RoleName.SEER, RoleName.WITCH, RoleName.HUNTER)
        + (RoleName.VILLAGER,) * villagers
    )


# D-056, written out. The wolves are the only count that moves; the six-player
# table is knowingly favourable to the village, which D-061 exists to correct.
DEFAULT_COMPOSITIONS: dict[int, Composition] = {
    6: Composition(roles=_table(werewolves=1, villagers=2)),
    7: Composition(roles=_table(werewolves=2, villagers=2)),
    8: Composition(roles=_table(werewolves=2, villagers=3)),
}


def default_composition(player_count: int) -> Composition:
    """Return the table V1 deals for that many players."""
    try:
        return DEFAULT_COMPOSITIONS[player_count]
    except KeyError as unsupported:
        raise UnsupportedPlayerCountError(
            f"V1 supports {MINIMUM_PLAYERS} to {MAXIMUM_PLAYERS} players, not {player_count}"
        ) from unsupported
