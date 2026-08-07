"""Setting the table: who sits where, who was dealt what, and where the game is.

Seats are public and roles are not, which is the first place the visibility
model earns its keep: a journal filtered for one player still opens on a whole
table (D-009, D-032).
"""

from typing import Literal

from pydantic import Field

from lupus_ex_machina.engine.events.fact import EventKind, Fact
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.visibility import Visibility


class PlayerSeated(Fact):
    """A player takes their seat. Identities and seats are public from the start."""

    kind: Literal[EventKind.PLAYER_SEATED] = EventKind.PLAYER_SEATED
    player: PlayerId
    name: str
    seat: int = Field(ge=0)

    @property
    def audience(self) -> Visibility:
        """Public: everyone sees who sits where."""
        return Visibility.public()


class RoleAssigned(Fact):
    """A player is dealt their role — the one secret the whole game turns on."""

    kind: Literal[EventKind.ROLE_ASSIGNED] = EventKind.ROLE_ASSIGNED
    player: PlayerId
    role: RoleName

    @property
    def audience(self) -> Visibility:
        """That player alone."""
        return Visibility.for_player(self.player)


class PackRevealed(Fact):
    """The wolves meet on Night 0, without speaking (D-032)."""

    kind: Literal[EventKind.PACK_REVEALED] = EventKind.PACK_REVEALED
    members: tuple[PlayerId, ...]

    @property
    def audience(self) -> Visibility:
        """The pack, and nobody else at the table."""
        return Visibility.for_role(RoleName.WEREWOLF)


class PhaseEntered(Fact):
    """The game moves to another phase."""

    kind: Literal[EventKind.PHASE_ENTERED] = EventKind.PHASE_ENTERED
    phase: Phase
    day: int = Field(ge=0)

    @property
    def audience(self) -> Visibility:
        """Public: the rhythm of the game is shared by everyone."""
        return Visibility.public()
