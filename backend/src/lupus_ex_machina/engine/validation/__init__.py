"""Legality of intents.

Validation answers a question, it never applies anything: it takes a state and
an intent and either returns quietly or raises :class:`IllegalIntentError` with a
reason. Keeping it free of effects is what makes a refusal harmless — a rejected
intent can never leave a trace in the state (J2.3.4).

Legality is the engine's business, not the agents' (D-001). Language models
produce illegal actions routinely, so these refusals are a normal part of a
game, not an exceptional path.

The judgement is split the way the intents are: :mod:`actor` for the two players
a move involves, :mod:`turn` for the floor and the ballot, :mod:`powers` for what
a role may play.
"""

from typing import assert_never

from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.intents import Intent, RoleAction, SharePriority, TakeTurn, Wait
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation.actor import ACTIONABLE_PHASES, ensure_actor_may_act
from lupus_ex_machina.engine.validation.powers import (
    validate_priority_share,
    validate_role_action,
)
from lupus_ex_machina.engine.validation.turn import BOOTSTRAP_DAY, validate_turn


def validate_intent(state: GameState, actor: PlayerId, intent: Intent) -> None:
    """Raise :class:`IllegalIntentError` when the actor may not play that intent."""
    ensure_actor_may_act(state, actor)

    match intent:
        case Wait():
            _validate_waiting(state)
        case TakeTurn():
            validate_turn(state, actor, intent)
        case RoleAction():
            validate_role_action(state, actor, intent)
        case SharePriority():
            validate_priority_share(state, actor, intent)
        case _:  # pragma: no cover - the union is closed, mypy proves this is dead
            assert_never(intent)


def _validate_waiting(state: GameState) -> None:
    """Doing nothing with one's turn is legal, and a table may forbid it (D-048).

    Only during the debate. Night 0 offers no action at all (D-032), and a night
    calls nobody who has nothing to do, so refusing silence there would deadlock
    a round rather than sharpen it.
    """
    if state.phase is Phase.DAY and not state.rules.debate.waiting_allowed:
        raise IllegalIntentError("This game does not allow waiting out the debate")


__all__ = [
    "ACTIONABLE_PHASES",
    "BOOTSTRAP_DAY",
    "validate_intent",
]
