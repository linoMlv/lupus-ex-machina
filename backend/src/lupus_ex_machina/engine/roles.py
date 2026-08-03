"""Teams and roles.

Roles are declarative objects held in a registry rather than plain constants
(D-010): a role carries data the engine reads — its team, whether it acts at
night, and in which order it wakes. The powered roles (seer, witch, hunter) join
the registry in J4; J2 only needs the two teams to exist.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Team(StrEnum):
    """Side a player wins with."""

    VILLAGE = "village"
    WEREWOLVES = "werewolves"


class RoleName(StrEnum):
    """Roles known to the engine."""

    VILLAGER = "villager"
    WEREWOLF = "werewolf"


class Role(BaseModel):
    """Declarative description of a role."""

    model_config = ConfigDict(frozen=True)

    name: RoleName
    team: Team
    wakes_at_night: bool = False
    wake_order: int | None = None


ROLES: dict[RoleName, Role] = {
    RoleName.VILLAGER: Role(name=RoleName.VILLAGER, team=Team.VILLAGE),
    RoleName.WEREWOLF: Role(
        name=RoleName.WEREWOLF,
        team=Team.WEREWOLVES,
        wakes_at_night=True,
        wake_order=20,
    ),
}


def team_of(role: RoleName) -> Team:
    """Return the team a role belongs to."""
    return ROLES[role].team
