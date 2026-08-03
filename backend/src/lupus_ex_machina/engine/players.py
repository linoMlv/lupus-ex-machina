"""Players.

A player is immutable: killing one produces a new player, never a mutation
(J2.1.4). Identity and seat are separate on purpose — the seat drives the
placement on the 3D circle, the identity never changes.
"""

from typing import NewType

from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.engine.roles import RoleName, Team, team_of

PlayerId = NewType("PlayerId", str)


class Player(BaseModel):
    """A participant of the game, alive or dead."""

    model_config = ConfigDict(frozen=True)

    id: PlayerId
    name: str
    seat: int = Field(ge=0)
    role: RoleName
    alive: bool = True

    @property
    def team(self) -> Team:
        """Team this player wins with."""
        return team_of(self.role)

    def killed(self) -> "Player":
        """Return the same player, dead."""
        return self.model_copy(update={"alive": False})
