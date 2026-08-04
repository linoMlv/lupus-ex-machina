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

from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.intents import (
    PRIORITY_BUDGET,
    Intent,
    IntentKind,
    PriorityPoint,
    RoleAction,
    SharePriority,
    TakeTurn,
    Vote,
    Wait,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import ROLES, RoleActionName, RoleName, Team
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import (
    BOOTSTRAP_DAY,
    validate_intent,
)


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
    may_speak: bool = False
    """Whether this player still holds the floor (D-013)."""
    may_vote: bool = False
    """Whether this player may still cast a ballot this round (D-024).

    Told apart from :attr:`may_speak` because one turn can do either, both, or
    neither (D-028): the kind of intent alone would not say which halves of it
    the rules would take.
    """
    vote_targets: tuple[PlayerId, ...] = ()
    action_targets: tuple[PlayerId, ...] = ()
    available_actions: tuple[RoleActionName, ...] = ()
    """Powers this player may use right now, empty when they have none."""
    priority_budget: int = 0
    """Points this player may spread over the prey tonight, zero when they may not."""

    @property
    def living_others(self) -> tuple[PlayerId, ...]:
        """Living players other than oneself."""
        return tuple(
            player.id for player in self.players if player.alive and player.id != self.self_id
        )


def project(state: GameState, viewer: PlayerId) -> PlayerView:
    """Build what ``viewer`` is allowed to know about the current state.

    The legal moves are settled by putting candidates to the validator, so each
    answer is worked out once here and handed down rather than recomputed by
    every field that needs it.
    """
    actions = _available_actions(state, viewer)
    designating = _may_designate(state, viewer)
    speaking = _accepted(state, viewer, TakeTurn(speech="Je vous écoute."))
    voting = _accepted(state, viewer, TakeTurn(vote=Vote()))

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
        allowed_intents=_allowed_intents(
            state, viewer, actions, designating=designating, taking_a_turn=speaking or voting
        ),
        may_speak=speaking,
        may_vote=voting,
        vote_targets=_vote_targets(state, viewer),
        action_targets=_action_targets(state, viewer, actions, designating=designating),
        available_actions=actions,
        priority_budget=PRIORITY_BUDGET if designating else 0,
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
    """Whether the rules would take anything at all from this player right now.

    Asked of the validator rather than restated: the dead usually have no move,
    except for the hunter who owes a shot, and a second description of that
    exception is a second place to get it wrong.
    """
    return _accepted(state, viewer, Wait()) or bool(_available_actions(state, viewer))


def _accepted(state: GameState, viewer: PlayerId, intent: Intent) -> bool:
    """Whether the rules would let this player play that move right now."""
    try:
        validate_intent(state, viewer, intent)
    except IllegalIntentError:
        return False
    return True


def _allowed_intents(
    state: GameState,
    viewer: PlayerId,
    actions: tuple[RoleActionName, ...],
    *,
    designating: bool,
    taking_a_turn: bool,
) -> tuple[IntentKind, ...]:
    """The moves the validator would accept, asked one by one.

    Every kind is put to the validator on a move that stands for it, so the view
    is the acceptance rather than a description of it. That is the one class of
    bug this projection can produce, and it is worth spending a few calls on.

    Which *halves* of a turn are open is said by :attr:`PlayerView.may_speak`
    and :attr:`PlayerView.may_vote`: one kind covers all three shapes a turn
    can take (D-028), so the kind alone would not be enough to act on.
    """
    offered = [IntentKind.WAIT] if _accepted(state, viewer, Wait()) else []
    if taking_a_turn:
        offered.append(IntentKind.TAKE_TURN)

    if designating:
        offered.append(IntentKind.SHARE_PRIORITY)
    if actions:
        offered.append(IntentKind.ROLE_ACTION)

    return tuple(sorted(offered))


def _may_designate(state: GameState, viewer: PlayerId) -> bool:
    """Whether this player may still weigh the prey tonight (D-008)."""
    return any(
        _accepted(
            state,
            viewer,
            SharePriority(allocations=(PriorityPoint(target=candidate.id, points=1),)),
        )
        for candidate in state.living
    )


def _available_actions(state: GameState, viewer: PlayerId) -> tuple[RoleActionName, ...]:
    """Single-target powers this player may use right now.

    Candidates come from the registry, so a role gains its move by being
    declared (D-010); which of them survive is settled by putting each to the
    validator, phase and all.
    """
    role = ROLES[state.player(viewer).role]
    return tuple(
        sorted(
            action
            for action in role.actions
            if any(
                _accepted(state, viewer, RoleAction(action=action, target=candidate.id))
                for candidate in state.living
            )
        )
    )


def _action_targets(
    state: GameState,
    viewer: PlayerId,
    actions: tuple[RoleActionName, ...],
    *,
    designating: bool,
) -> tuple[PlayerId, ...]:
    """Whom this player may aim at right now, whichever of their powers they use.

    A witch holding two potions sees the union of what each of them reaches —
    the choice of potion is hers.
    """
    if not designating and not actions:
        return ()

    return tuple(
        player.id
        for player in state.living
        if (
            designating
            and _accepted(
                state,
                viewer,
                SharePriority(allocations=(PriorityPoint(target=player.id, points=1),)),
            )
        )
        or any(
            _accepted(state, viewer, RoleAction(action=action, target=player.id))
            for action in actions
        )
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
