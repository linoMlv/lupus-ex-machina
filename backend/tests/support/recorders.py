"""Journals to replay, and the agent that records one."""

from lupus_ex_machina.engine.events import (
    EventPayload,
    PackRevealed,
    PhaseEntered,
    PlayerSeated,
    RoleAssigned,
)
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.state import GameState

WOLF = Player(id=PlayerId("p0"), name="Adèle", seat=0, role=RoleName.WEREWOLF)
VILLAGER = Player(id=PlayerId("p1"), name="Basile", seat=1, role=RoleName.VILLAGER)
OTHER_VILLAGER = Player(id=PlayerId("p2"), name="Camille", seat=2, role=RoleName.VILLAGER)

TABLE = (WOLF, VILLAGER, OTHER_VILLAGER)


class Recorder:
    """Writes a journal the way the engine does, for a table known in advance."""

    def __init__(self) -> None:
        """Seat the table and deal the roles."""
        self.journal = Journal()
        self.state = GameState.initial(TABLE)

        for player in TABLE:
            self._write(PlayerSeated(player=player.id, name=player.name, seat=player.seat))
        for player in TABLE:
            self._write(RoleAssigned(player=player.id, role=player.role))
        self._write(PackRevealed(members=(WOLF.id,)))
        self._write(PhaseEntered(phase=Phase.NIGHT_ZERO, day=0))

    def _write(self, payload: EventPayload) -> None:
        self.journal.record(payload, at=self.state)

    def enter(self, phase: Phase, *, day: int | None = None) -> "Recorder":
        """Move to another phase, exactly as the engine would."""
        self.state = self.state.entering(phase, day=day)
        self._write(PhaseEntered(phase=self.state.phase, day=self.state.day))
        return self

    def write(self, payload: EventPayload) -> "Recorder":
        """Record one more fact."""
        self._write(payload)
        return self
