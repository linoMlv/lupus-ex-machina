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


class DeathTrigger(StrEnum):
    """What a role sets off by dying."""

    AVENGING_SHOT = "avenging_shot"


class Role(BaseModel):
    """Declarative description of a role."""

    model_config = ConfigDict(frozen=True)

    name: RoleName
    team: Team
    wake_order: int | None = None
    actions: frozenset[RoleActionName] = frozenset()
    on_death: DeathTrigger | None = None

    @property
    def wakes_at_night(self) -> bool:
        """Whether the night calls this role at all.

        Read off the wake order rather than declared beside it: two fields
        saying the same thing are two fields that end up disagreeing.
        """
        return self.wake_order is not None


# The order of the night is a rule, not a preference. The witch learns whom the
# pack took (D-029), so she cannot be woken before it has chosen; the seer goes
# first, as at a real table. The gaps leave room for the roles a later version
# adds without renumbering the ones already here.
SEER_WAKES = 10
WEREWOLVES_WAKE = 20
WITCH_WAKES = 30


ROLES: dict[RoleName, Role] = {
    RoleName.VILLAGER: Role(name=RoleName.VILLAGER, team=Team.VILLAGE),
    RoleName.WEREWOLF: Role(
        name=RoleName.WEREWOLF,
        team=Team.WEREWOLVES,
        wake_order=WEREWOLVES_WAKE,
        actions=frozenset({RoleActionName.DEVOUR}),
    ),
    RoleName.SEER: Role(
        name=RoleName.SEER,
        team=Team.VILLAGE,
        wake_order=SEER_WAKES,
        actions=frozenset({RoleActionName.INSPECT}),
    ),
    RoleName.WITCH: Role(
        name=RoleName.WITCH,
        team=Team.VILLAGE,
        wake_order=WITCH_WAKES,
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
