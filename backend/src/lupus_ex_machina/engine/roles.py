"""Teams, roles, and what each one is allowed to do.

Roles are declarative objects held in a registry rather than constants scattered
through the engine (D-010): a role carries the data the rules read — its team,
when it wakes, what it may do, and what its death sets off. It carries no
behaviour. Modelling a role in configuration alone was rejected because a role
holds logic that always overflows the declarative; declaring the *shape* here and
keeping the rules in the engine is the compromise that leaves both readable.

``on_death`` is that compromise made concrete. D-010 called for hooks, and hooks
in the shape of callables would bury a slice of the resolution inside a data
table. A closed enum of triggers says the same thing, stays comparable, and
leaves the rules where they can be read in order.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Team(StrEnum):
    """Side a player wins with."""

    VILLAGE = "village"
    WEREWOLVES = "werewolves"


class RoleName(StrEnum):
    """Roles known to the engine (D-015)."""

    VILLAGER = "villager"
    WEREWOLF = "werewolf"
    SEER = "seer"
    WITCH = "witch"
    HUNTER = "hunter"


class RoleActionName(StrEnum):
    """What a role does when it acts.

    ``DEVOUR`` is the pack's, and the pack expresses it collectively: each wolf
    spreads a budget of points over the prey it would rather take, and the
    designation is the tally (D-008). The others are played on a single target.
    """

    DEVOUR = "devour"
    INSPECT = "inspect"
    HEAL = "heal"
    POISON = "poison"
    SHOOT = "shoot"


#: Powers that work once in a whole game rather than once a night. Stated in one
#: place because two things read it — the night, which spends them, and the
#: replay, which has to spend them again to rebuild the same game.
ONE_SHOT_ACTIONS = frozenset({RoleActionName.HEAL, RoleActionName.POISON, RoleActionName.SHOOT})


class DeathTrigger(StrEnum):
    """What a role sets off by dying."""

    AVENGING_SHOT = "avenging_shot"


class Role(BaseModel):
    """Declarative description of a role."""

    model_config = ConfigDict(frozen=True)

    name: RoleName
    team: Team
    wakes_at_night: bool = False
    """Whether the night calls this role at all.

    Declared, but *when* it is called is not: the order is a setting the night
    reads (D-069), so the registry saying it too would be a second place for the
    rank to be wrong. What belongs here is the structural half — a role either
    acts at night or it does not.
    """

    actions: frozenset[RoleActionName] = frozenset()
    on_death: DeathTrigger | None = None


ROLES: dict[RoleName, Role] = {
    RoleName.VILLAGER: Role(name=RoleName.VILLAGER, team=Team.VILLAGE),
    RoleName.WEREWOLF: Role(
        name=RoleName.WEREWOLF,
        team=Team.WEREWOLVES,
        wakes_at_night=True,
        actions=frozenset({RoleActionName.DEVOUR}),
    ),
    RoleName.SEER: Role(
        name=RoleName.SEER,
        team=Team.VILLAGE,
        wakes_at_night=True,
        actions=frozenset({RoleActionName.INSPECT}),
    ),
    RoleName.WITCH: Role(
        name=RoleName.WITCH,
        team=Team.VILLAGE,
        wakes_at_night=True,
        actions=frozenset({RoleActionName.HEAL, RoleActionName.POISON}),
    ),
    # The hunter never wakes: the shot is always fired by day and in front of
    # everyone, even when the night is what killed them (D-030).
    RoleName.HUNTER: Role(
        name=RoleName.HUNTER,
        team=Team.VILLAGE,
        actions=frozenset({RoleActionName.SHOOT}),
        on_death=DeathTrigger.AVENGING_SHOT,
    ),
}


def team_of(role: RoleName) -> Team:
    """Return the team a role belongs to."""
    return ROLES[role].team
