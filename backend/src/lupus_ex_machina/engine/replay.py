"""Rebuilding the state of a game from its journal.

The state is derived from the journal, never stored beside it (D-040). That is
what makes the journal the source of truth: a state the journal cannot produce
would be information nobody ever gave an audience to.

Replay walks the same phase machine as the game itself, so a journal describing
an impossible game is refused instead of being turned into a plausible-looking
state. Truncated files happen; a silently wrong game is worse than a loud
failure.

Facts and effects are kept apart on purpose. A fact knows who may see it — that
is intrinsic to it — but what it does to the state is the engine's business, so
it lives here, in one exhaustive match the type checker proves complete.
"""

from collections.abc import Iterable
from typing import assert_never

from lupus_ex_machina.engine.errors import EngineError, IllegalTransitionError
from lupus_ex_machina.engine.events import (
    BallotAnnounced,
    BallotCast,
    Event,
    GameEnded,
    IntentRejected,
    NightResolved,
    NotebookEntryRecorded,
    PackRevealed,
    PackSpeechDelivered,
    PhaseEntered,
    PlayerSeated,
    PriorityShared,
    PrivateReasoningRecorded,
    RoleAssigned,
    RoleRevealed,
    RunoffOpened,
    SpeechDelivered,
    VoteResolved,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.state import GameState


class JournalReplayError(EngineError):
    """A journal that no real game could have produced."""


def replay(events: Iterable[Event]) -> GameState:
    """Rebuild the state a journal leads to."""
    rebuild = _Replay()
    for event in events:
        rebuild.apply(event)
    return rebuild.state


class _Replay:
    """The state being rebuilt, and the table it is being rebuilt for.

    Seats and roles arrive as separate facts, because they have separate
    audiences: where everyone sits is public, what they were dealt is not. The
    game itself only exists once both are known, which is the moment Night 0
    opens.
    """

    def __init__(self) -> None:
        self._seats: dict[PlayerId, PlayerSeated] = {}
        self._roles: dict[PlayerId, RoleName] = {}
        self._state: GameState | None = None

    @property
    def state(self) -> GameState:
        """The state the journal leads to."""
        if self._state is None:
            raise JournalReplayError("This journal holds no game that ever started")
        return self._state

    def _running(self) -> GameState:
        """The state a fact is about, refusing facts that precede the game itself."""
        if self._state is None:
            raise JournalReplayError("A fact was recorded about a game that has not started")
        return self._state

    def apply(self, event: Event) -> None:
        """Fold one fact into the state."""
        match event.payload:
            case PlayerSeated() as seated:
                self._seat(seated)
            case RoleAssigned() as dealt:
                self._deal(dealt)
            case PhaseEntered() as entered:
                self._enter(entered)
            case BallotCast() as ballot:
                self._state = self._running().with_ballot_from(ballot.voter, ballot.target)
            case PriorityShared() as spread:
                self._state = self._running().with_priority_share_from(
                    spread.actor, spread.allocations
                )
            case RunoffOpened() as runoff:
                self._state = self._running().reopened_for_runoff(runoff.targets)
            case VoteResolved(eliminated=victim) | NightResolved(victim=victim):
                self._close_round(victim)
            case (
                PackRevealed()
                | SpeechDelivered()
                | PackSpeechDelivered()
                | BallotAnnounced()
                | RoleRevealed()
                | GameEnded()
                | IntentRejected()
                | PrivateReasoningRecorded()
                | NotebookEntryRecorded()
            ):
                # Information, not effect: these facts tell the story without
                # changing what the state holds.
                return
            case _:  # pragma: no cover - the union is closed, mypy proves this is dead
                assert_never(event.payload)

    # --- Setting the table ---------------------------------------------------

    def _seat(self, seated: PlayerSeated) -> None:
        if seated.player in self._seats:
            raise JournalReplayError(f"Player {seated.player} took a seat twice")
        self._seats[seated.player] = seated

    def _deal(self, dealt: RoleAssigned) -> None:
        if dealt.player not in self._seats:
            raise JournalReplayError(f"Player {dealt.player} never took a seat")
        self._roles[dealt.player] = dealt.role

    def _table(self) -> tuple[Player, ...]:
        """Build the players, in seat order — the order a game deals them in."""
        missing = self._seats.keys() - self._roles.keys()
        if missing:
            raise JournalReplayError(f"No role was ever dealt to {sorted(missing)}")

        return tuple(
            Player(
                id=seated.player,
                name=seated.name,
                seat=seated.seat,
                role=self._roles[seated.player],
            )
            for seated in sorted(self._seats.values(), key=lambda seated: seated.seat)
        )

    # --- Running the game ----------------------------------------------------

    def _enter(self, entered: PhaseEntered) -> None:
        if self._state is None:
            self._open(entered)
            return

        try:
            self._state = self._state.entering(entered.phase, day=entered.day)
        except IllegalTransitionError as illegal:
            raise JournalReplayError(str(illegal)) from illegal

    def _open(self, entered: PhaseEntered) -> None:
        """Start the game, which can only ever happen on Night 0 (D-032)."""
        if entered.phase is not Phase.NIGHT_ZERO:
            raise JournalReplayError(f"A game opens on Night 0, not on {entered.phase}")
        self._state = GameState.initial(self._table())

    def _close_round(self, victim: PlayerId | None) -> None:
        """Apply a resolution: the dead, then the round wiped clean."""
        running = self._running()
        state = running if victim is None else running.with_players_killed([victim])
        self._state = state.cleared_of_round_choices()
