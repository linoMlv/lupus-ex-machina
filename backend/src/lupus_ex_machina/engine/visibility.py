"""Who may know what (D-009).

Every fact the game produces carries a visibility, and a view is the result of
filtering on it. The point is not the filter itself but what it replaces: each
configurable option about information — revealing the role of the dead, a
speaking seer, a public vote history — becomes a change of visibility instead of
a condition scattered through the engine, the network layer and the display.

Two rules hold this module together:

* A visibility cannot be malformed. ``role`` without a role, or ``public``
  carrying an audience, are refused at construction — a contradiction here would
  not raise, it would leak.
* The spectator is a recipient like any other. Omniscience is expressed inside
  the predicate, never as a caller that skips it, because a bypass is where a
  leak eventually hides (D-046).
"""

from enum import StrEnum
from typing import Self, assert_never

from pydantic import BaseModel, ConfigDict, model_validator

from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleName


class VisibilityScope(StrEnum):
    """The audiences a fact can be addressed to."""

    PUBLIC = "public"
    ROLE = "role"
    PLAYER = "player"
    SPECTATOR = "spectator"


class Recipient(BaseModel):
    """Whoever a projection is built for: a player, or the spectator.

    A player recipient carries their role because ``role:<x>`` visibilities are
    resolved against it. Being alive plays no part: the dead keep watching the
    game, so they keep receiving the facts that were theirs.
    """

    model_config = ConfigDict(frozen=True)

    player: PlayerId | None = None
    role: RoleName | None = None

    @classmethod
    def of(cls, player: Player) -> "Recipient":
        """Build the recipient a given player is."""
        return cls(player=player.id, role=player.role)

    @property
    def is_spectator(self) -> bool:
        """Whether this recipient watches from outside the game."""
        return self.player is None

    @model_validator(mode="after")
    def _identity_is_whole(self) -> Self:
        """Refuse a recipient that is half a player and half the spectator."""
        if (self.player is None) != (self.role is None):
            raise ValueError("A recipient carries either both an identity and a role, or neither")
        return self


#: The omniscient recipient. It sees every fact, through the same predicate.
SPECTATOR = Recipient()


class Visibility(BaseModel):
    """The audience a single fact is addressed to."""

    model_config = ConfigDict(frozen=True)

    scope: VisibilityScope
    role: RoleName | None = None
    player: PlayerId | None = None

    @classmethod
    def public(cls) -> "Visibility":
        """Everyone at the table, and the spectator."""
        return cls(scope=VisibilityScope.PUBLIC)

    @classmethod
    def for_role(cls, role: RoleName) -> "Visibility":
        """Whoever holds that role — the private channel of a pack, say."""
        return cls(scope=VisibilityScope.ROLE, role=role)

    @classmethod
    def for_player(cls, player: PlayerId) -> "Visibility":
        """That player alone: their own role, their own thoughts."""
        return cls(scope=VisibilityScope.PLAYER, player=player)

    @classmethod
    def spectator_only(cls) -> "Visibility":
        """Nobody at the table. What the audience is shown and the players are not."""
        return cls(scope=VisibilityScope.SPECTATOR)

    def reaches(self, recipient: Recipient) -> bool:
        """Whether that recipient is entitled to this fact."""
        if recipient.is_spectator:
            return True

        match self.scope:
            case VisibilityScope.PUBLIC:
                return True
            case VisibilityScope.ROLE:
                return recipient.role == self.role
            case VisibilityScope.PLAYER:
                return recipient.player == self.player
            case VisibilityScope.SPECTATOR:
                return False
            case _:  # pragma: no cover - the enum is closed, mypy proves this is dead
                assert_never(self.scope)

    @model_validator(mode="after")
    def _audience_matches_scope(self) -> Self:
        """Refuse a visibility whose audience contradicts its scope.

        Each scope needs exactly one shape: a role for ``role``, a player for
        ``player``, nothing for the other two. Anything else is a contradiction
        that ``reaches`` would resolve silently, and silently in the permissive
        direction.
        """
        required: dict[VisibilityScope, tuple[bool, bool]] = {
            VisibilityScope.PUBLIC: (False, False),
            VisibilityScope.ROLE: (True, False),
            VisibilityScope.PLAYER: (False, True),
            VisibilityScope.SPECTATOR: (False, False),
        }

        if (self.role is not None, self.player is not None) != required[self.scope]:
            raise ValueError(f"A '{self.scope}' visibility cannot carry this audience")
        return self
