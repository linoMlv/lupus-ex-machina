"""Deaths and the end of the game — the loud, public part of the record.

Death is never hidden (D-072). Only the *role* of the deceased is a setting, and
the option decides whether the fact happens at all, never who may read it
(D-009, D-080).
"""

from typing import Literal

from lupus_ex_machina.engine.events.fact import EventKind, Fact
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.victory import Outcome
from lupus_ex_machina.engine.visibility import Visibility


class ShotFired(Fact):
    """A hunter took someone along as he died (D-030).

    Public, and loudly so: the shot is fired by day and in front of everyone,
    which is half of what makes the role worth playing.
    """

    kind: Literal[EventKind.SHOT_FIRED] = EventKind.SHOT_FIRED
    hunter: PlayerId
    target: PlayerId
    chosen_by_the_hunter: bool
    """False when the hunter would not aim and the engine aimed for him (D-055)."""

    @property
    def audience(self) -> Visibility:
        """Public."""
        return Visibility.public()


class RoleRevealed(Fact):
    """The role of a player who just died, when the configuration allows it (D-072)."""

    kind: Literal[EventKind.ROLE_REVEALED] = EventKind.ROLE_REVEALED
    player: PlayerId
    role: RoleName

    @property
    def audience(self) -> Visibility:
        """Public — the option decides whether the fact happens at all, not who sees it."""
        return Visibility.public()


class GameEnded(Fact):
    """A side has won (D-059)."""

    kind: Literal[EventKind.GAME_ENDED] = EventKind.GAME_ENDED
    outcome: Outcome

    @property
    def audience(self) -> Visibility:
        """Public."""
        return Visibility.public()
