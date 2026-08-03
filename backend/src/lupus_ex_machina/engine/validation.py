"""Legality of intents.

Validation answers a question, it never applies anything: it takes a state and
an intent and either returns quietly or raises :class:`IllegalIntentError` with a
reason. Keeping it free of effects is what makes a refusal harmless — a rejected
intent can never leave a trace in the state (J2.3.4).

Legality is the engine's business, not the agents' (D-001). Language models
produce illegal actions routinely, so these refusals are a normal part of a
game, not an exceptional path.
"""

from typing import assert_never

from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.intents import (
    CastVote,
    Intent,
    RoleAction,
    RoleActionName,
    Speak,
    Wait,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import Team
from lupus_ex_machina.engine.state import GameState

# Day 1 is a bootstrap round: the debate opens with nothing to go on, so nobody
# may be named yet and a blank vote is the only way out (D-032).
BOOTSTRAP_DAY = 1

ACTIONABLE_PHASES = frozenset({Phase.NIGHT_ZERO, Phase.DAY, Phase.NIGHT})


def validate_intent(state: GameState, actor: PlayerId, intent: Intent) -> None:
    """Raise :class:`IllegalIntentError` when the actor may not play that intent."""
    _ensure_actor_may_act(state, actor)

    match intent:
        case Wait():
            return
        case Speak():
            _validate_speech(state, actor)
        case CastVote():
            _validate_vote(state, actor, intent)
        case RoleAction():
            _validate_role_action(state, actor, intent)
        case _:  # pragma: no cover - the union is closed, mypy proves this is dead
            assert_never(intent)


# --- Actor ------------------------------------------------------------------


def _ensure_actor_may_act(state: GameState, actor: PlayerId) -> None:
    _ensure_known(state, actor)
    if not state.is_alive(actor):
        raise IllegalIntentError(f"Player {actor} is dead and cannot act")
    if state.phase not in ACTIONABLE_PHASES:
        raise IllegalIntentError(f"No intent is accepted during phase {state.phase}")


def _ensure_known(state: GameState, player: PlayerId) -> None:
    if not state.has_player(player):
        raise IllegalIntentError(f"Unknown player {player}")


def _ensure_alive_target(state: GameState, target: PlayerId) -> None:
    _ensure_known(state, target)
    if not state.is_alive(target):
        raise IllegalIntentError(f"Player {target} is dead and cannot be targeted")


# --- Speaking ---------------------------------------------------------------


def _validate_speech(state: GameState, actor: PlayerId) -> None:
    if state.phase is not Phase.DAY:
        raise IllegalIntentError("Speaking is only allowed during the day")
    _ensure_still_holds_the_floor(state, actor)


def _ensure_still_holds_the_floor(state: GameState, actor: PlayerId) -> None:
    """Voting gives up the right to speak for the rest of the round (D-013)."""
    if state.has_voted(actor):
        raise IllegalIntentError(f"Player {actor} has already voted and lost the floor")


# --- Voting -----------------------------------------------------------------


def _validate_vote(state: GameState, actor: PlayerId, intent: CastVote) -> None:
    if state.phase is not Phase.DAY:
        raise IllegalIntentError("Voting is only allowed during the day")
    if state.has_voted(actor):
        raise IllegalIntentError(f"Player {actor} has already voted, and a vote is final")

    if intent.target is None:
        return

    if state.day == BOOTSTRAP_DAY:
        raise IllegalIntentError("On the first day, only a blank vote is allowed")
    _ensure_alive_target(state, intent.target)


# --- Night actions ----------------------------------------------------------


def _validate_role_action(state: GameState, actor: PlayerId, intent: RoleAction) -> None:
    if state.phase is not Phase.NIGHT:
        raise IllegalIntentError("Role actions are only allowed at night")

    match intent.action:
        case RoleActionName.DEVOUR:
            _validate_devouring(state, actor, intent.target)
        case _:  # pragma: no cover - the enum is closed, mypy proves this is dead
            assert_never(intent.action)


def _validate_devouring(state: GameState, actor: PlayerId, target: PlayerId) -> None:
    if state.player(actor).team is not Team.WEREWOLVES:
        raise IllegalIntentError(f"Player {actor} is not a werewolf and cannot devour")
    if state.has_chosen_a_night_target(actor):
        raise IllegalIntentError(f"Player {actor} has already designated a target tonight")

    _ensure_alive_target(state, target)
    if state.player(target).team is Team.WEREWOLVES:
        raise IllegalIntentError("A werewolf cannot devour a player of its own team")
