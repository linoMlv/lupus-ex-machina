"""What the rules would take from a player right now, asked of the validator.

Every answer here is settled by putting a candidate move to
:func:`validate_intent` rather than by restating the rules. That is deliberate,
and it closes the failure mode this architecture is prone to: the view is what a
model is *told* it may do, the validator is what is *accepted*, and any gap
between the two is invisible until an agent built from the view walks into it.

Offering is therefore accepting, in the one place both are decided.
"""

from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.intents import (
    Intent,
    IntentKind,
    PriorityPoint,
    RoleAction,
    SharePriority,
    Wait,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import ROLES, RoleActionName
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import BOOTSTRAP_DAY, validate_intent


def accepted(state: GameState, viewer: PlayerId, intent: Intent) -> bool:
    """Whether the rules would let this player play that move right now."""
    try:
        validate_intent(state, viewer, intent)
    except IllegalIntentError:
        return False
    return True


def may_act(state: GameState, viewer: PlayerId) -> bool:
    """Whether the rules would take anything at all from this player right now.

    Asked of the validator rather than restated: the dead usually have no move,
    except for the hunter who owes a shot, and a second description of that
    exception is a second place to get it wrong.
    """
    return accepted(state, viewer, Wait()) or bool(available_actions(state, viewer))


def allowed_intents(
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

    Which *halves* of a turn are open is said by ``PlayerView.may_speak`` and
    ``PlayerView.may_vote``: one kind covers all three shapes a turn can take
    (D-028), so the kind alone would not be enough to act on.
    """
    offered = [IntentKind.WAIT] if accepted(state, viewer, Wait()) else []
    if taking_a_turn:
        offered.append(IntentKind.TAKE_TURN)

    if designating:
        offered.append(IntentKind.SHARE_PRIORITY)
    if actions:
        offered.append(IntentKind.ROLE_ACTION)

    return tuple(sorted(offered))


def may_designate(state: GameState, viewer: PlayerId) -> bool:
    """Whether this player may still weigh the prey tonight (D-008)."""
    return any(
        accepted(
            state,
            viewer,
            SharePriority(allocations=(PriorityPoint(target=candidate.id, points=1),)),
        )
        for candidate in state.living
    )


def available_actions(state: GameState, viewer: PlayerId) -> tuple[RoleActionName, ...]:
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
                accepted(state, viewer, RoleAction(action=action, target=candidate.id))
                for candidate in state.living
            )
        )
    )


def action_targets(
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
            and accepted(
                state,
                viewer,
                SharePriority(allocations=(PriorityPoint(target=player.id, points=1),)),
            )
        )
        or any(
            accepted(state, viewer, RoleAction(action=action, target=player.id))
            for action in actions
        )
    )


def vote_targets(state: GameState, viewer: PlayerId) -> tuple[PlayerId, ...]:
    """Players this one may name. Empty on Day 1, where only a blank vote is legal (D-032).

    Never oneself: a player cannot vote for their own elimination, which the
    validator refuses too. Narrowed to the players a runoff is between while one
    is open (D-062).
    """
    if not may_act(state, viewer) or state.phase is not Phase.DAY:
        return ()
    if state.day == BOOTSTRAP_DAY or state.has_voted(viewer):
        return ()

    named = tuple(player.id for player in state.living if player.id != viewer)
    if not state.runoff_targets:
        return named
    return tuple(target for target in named if target in state.runoff_targets)
