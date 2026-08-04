"""Projection of the state onto what a single player may know.

An agent never receives :class:`GameState`; it receives this, and nothing else
reaches its prompt (D-001, GL-3). The rule is subtractive: the projection starts
from what is public and adds only what this player is entitled to — its own
role, and its pack if it has one.

The view also carries the moves that are currently legal. That is not a
convenience for the scripted agents: it is what a language model will be told it
may do (J7), and it keeps the legality in one place, next to the validator.

J3 generalises this into the visibility model, where each fact carries its own
audience (D-009). The boundary drawn here is the one that model will formalise.
"""

from pydantic import BaseModel, ConfigDict

from lupus_ex_machina.engine.intents import PRIORITY_BUDGET, IntentKind
from lupus_ex_machina.engine.night import prey_of
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import RoleName, Team
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import ACTIONABLE_PHASES, BOOTSTRAP_DAY


class PublicPlayer(BaseModel):
    """A player as everyone sees them: an identity, a seat, alive or dead.

    Death is always public; only the role of the deceased may stay hidden
    (D-072), and no role appears here at all.
    """

    model_config = ConfigDict(frozen=True)

    id: PlayerId
    name: str
    seat: int
    alive: bool


class PlayerView(BaseModel):
    """Everything one player knows about the game."""

    model_config = ConfigDict(frozen=True)

    self_id: PlayerId
    role: RoleName
    phase: Phase
    day: int
    players: tuple[PublicPlayer, ...]
    allies: tuple[PlayerId, ...] = ()
    voters: tuple[PlayerId, ...] = ()
    has_voted: bool = False
    allowed_intents: tuple[IntentKind, ...] = ()
    vote_targets: tuple[PlayerId, ...] = ()
    night_targets: tuple[PlayerId, ...] = ()
    priority_budget: int = 0
    """Points this player may spread over the prey tonight, zero when they may not."""

    @property
    def living_others(self) -> tuple[PlayerId, ...]:
        """Living players other than oneself."""
        return tuple(
            player.id for player in self.players if player.alive and player.id != self.self_id
        )


def project(state: GameState, viewer: PlayerId) -> PlayerView:
    """Build what ``viewer`` is allowed to know about the current state."""
    return PlayerView(
        self_id=viewer,
        role=state.player(viewer).role,
        phase=state.phase,
        day=state.day,
        players=tuple(
            PublicPlayer(id=player.id, name=player.name, seat=player.seat, alive=player.alive)
            for player in state.players
        ),
        allies=_allies_of(state, viewer),
        voters=tuple(ballot.voter for ballot in state.ballots),
        has_voted=state.has_voted(viewer),
        allowed_intents=_allowed_intents(state, viewer),
        vote_targets=_vote_targets(state, viewer),
        night_targets=_night_targets(state, viewer),
        priority_budget=PRIORITY_BUDGET if _may_designate(state, viewer) else 0,
    )


def _allies_of(state: GameState, viewer: PlayerId) -> tuple[PlayerId, ...]:
    """Wolves know each other; villagers know no one (D-032)."""
    if state.player(viewer).team is not Team.WEREWOLVES:
        return ()
    return tuple(
        player.id
        for player in state.players
        if player.team is Team.WEREWOLVES and player.id != viewer
    )


def _may_act(state: GameState, viewer: PlayerId) -> bool:
    """Whether the validator would accept anything at all from this player.

    The dead and the phases the engine resolves on its own offer no move. A view
    is built for them all the same — a dead player keeps watching the game — so
    it must say so rather than offer moves that would be refused.
    """
    return state.is_alive(viewer) and state.phase in ACTIONABLE_PHASES


def _allowed_intents(state: GameState, viewer: PlayerId) -> tuple[IntentKind, ...]:
    """List the moves the validator would accept right now."""
    if not _may_act(state, viewer):
        return ()

    if state.phase is Phase.DAY:
        if state.has_voted(viewer):
            return (IntentKind.WAIT,)
        return (IntentKind.SPEAK, IntentKind.VOTE, IntentKind.WAIT)

    if state.phase is Phase.NIGHT and state.player(viewer).team is Team.WEREWOLVES:
        # The pack keeps its own floor all night (D-007), and may spread its
        # points once (D-008).
        if _may_designate(state, viewer):
            return (IntentKind.SPEAK, IntentKind.SHARE_PRIORITY, IntentKind.WAIT)
        return (IntentKind.SPEAK, IntentKind.WAIT)

    return (IntentKind.WAIT,)


def _may_designate(state: GameState, viewer: PlayerId) -> bool:
    """Whether this player may still weigh the prey tonight."""
    return (
        _may_act(state, viewer)
        and state.phase is Phase.NIGHT
        and state.player(viewer).team is Team.WEREWOLVES
        and not state.has_acted_tonight(viewer)
    )


def _vote_targets(state: GameState, viewer: PlayerId) -> tuple[PlayerId, ...]:
    """Players this one may name. Empty on Day 1, where only a blank vote is legal (D-032).

    Never oneself: a player cannot vote for their own elimination, which the
    validator refuses too.
    """
    if not _may_act(state, viewer) or state.phase is not Phase.DAY:
        return ()
    if state.day == BOOTSTRAP_DAY or state.has_voted(viewer):
        return ()
    return tuple(player.id for player in state.living if player.id != viewer)


def _night_targets(state: GameState, viewer: PlayerId) -> tuple[PlayerId, ...]:
    """Prey the pack may weigh tonight.

    Read from the same place the validator reads it, so the offer and the
    acceptance cannot describe different tables.
    """
    if not _may_designate(state, viewer):
        return ()
    return tuple(player.id for player in prey_of(state))
