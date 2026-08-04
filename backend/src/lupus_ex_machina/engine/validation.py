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
from lupus_ex_machina.engine.hunter import hunters_owing_a_shot
from lupus_ex_machina.engine.intents import (
    PRIORITY_BUDGET,
    CastVote,
    Intent,
    RoleAction,
    SharePriority,
    Speak,
    Wait,
)
from lupus_ex_machina.engine.night import prey_of, victim_seen_by_the_witch
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.policy import InformationPolicy
from lupus_ex_machina.engine.roles import ROLES, RoleActionName, Team
from lupus_ex_machina.engine.state import GameState

# Day 1 is a bootstrap round: the debate opens with nothing to go on, so nobody
# may be named yet and a blank vote is the only way out (D-032).
BOOTSTRAP_DAY = 1

ACTIONABLE_PHASES = frozenset({Phase.NIGHT_ZERO, Phase.DAY, Phase.NIGHT, Phase.AVENGING_SHOT})


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
        case SharePriority():
            _validate_priority_share(state, actor, intent)
        case _:  # pragma: no cover - the union is closed, mypy proves this is dead
            assert_never(intent)


# --- Actor ------------------------------------------------------------------


def _ensure_actor_may_act(state: GameState, actor: PlayerId) -> None:
    """Only the living act — with one exception, and it is the whole point of it.

    A hunter fires as he dies (D-030). His shot is the single move the rules
    accept from a dead player, and it is accepted nowhere but in its own phase.
    """
    _ensure_known(state, actor)
    if state.phase not in ACTIONABLE_PHASES:
        raise IllegalIntentError(f"No intent is accepted during phase {state.phase}")
    if not state.is_alive(actor) and actor not in {owed.id for owed in hunters_owing_a_shot(state)}:
        raise IllegalIntentError(f"Player {actor} is dead and cannot act")


def _ensure_known(state: GameState, player: PlayerId) -> None:
    if not state.has_player(player):
        raise IllegalIntentError(f"Unknown player {player}")


def _ensure_alive_target(state: GameState, target: PlayerId) -> None:
    _ensure_known(state, target)
    if not state.is_alive(target):
        raise IllegalIntentError(f"Player {target} is dead and cannot be targeted")


# --- Speaking ---------------------------------------------------------------


def _validate_speech(state: GameState, actor: PlayerId) -> None:
    """The floor is public by day and the pack's own at night (D-007).

    Night 0 is silent for everyone: the wolves meet without speaking (D-032),
    which is a rule of the game rather than a limitation.
    """
    if state.phase is Phase.NIGHT:
        if state.player(actor).team is not Team.WEREWOLVES:
            raise IllegalIntentError(f"Player {actor} has nobody to talk to at night")
        return

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
    if intent.target == actor:
        raise IllegalIntentError(f"Player {actor} cannot vote for themselves")
    _ensure_alive_target(state, intent.target)


# --- Night actions ----------------------------------------------------------


def _validate_role_action(state: GameState, actor: PlayerId, intent: RoleAction) -> None:
    _ensure_the_role_owns_the_action(state, actor, intent.action)
    expected = Phase.AVENGING_SHOT if intent.action is RoleActionName.SHOOT else Phase.NIGHT
    if state.phase is not expected:
        raise IllegalIntentError(f"{intent.action} is not played during phase {state.phase}")

    match intent.action:
        case RoleActionName.DEVOUR:
            raise IllegalIntentError(
                "The pack designates its prey by spreading points, not one wolf at a time"
            )
        case RoleActionName.INSPECT:
            _validate_inspection(state, actor, intent.target)
        case RoleActionName.HEAL:
            _validate_healing(state, actor, intent.target)
        case RoleActionName.POISON:
            _validate_poisoning(state, actor, intent.target)
        case RoleActionName.SHOOT:
            _validate_the_shot(state, actor, intent.target)
        case _:  # pragma: no cover - the enum is closed, mypy proves this is dead
            assert_never(intent.action)


def _ensure_the_role_owns_the_action(
    state: GameState, actor: PlayerId, action: RoleActionName
) -> None:
    """A role may only play what its entry in the registry declares (D-010).

    Read from the registry rather than restated here, so the declaration and the
    rule that enforces it cannot drift apart.
    """
    role = ROLES[state.player(actor).role]
    if action not in role.actions:
        raise IllegalIntentError(f"A {role.name} cannot {action}")


def _validate_inspection(state: GameState, actor: PlayerId, target: PlayerId) -> None:
    """The seer reads one living player a night, and never herself (D-031)."""
    if state.has_acted_tonight(actor):
        raise IllegalIntentError(f"Player {actor} has already looked at someone tonight")
    if target == actor:
        raise IllegalIntentError(f"Player {actor} already knows what they are themselves")

    _ensure_alive_target(state, target)


def _validate_healing(state: GameState, actor: PlayerId, target: PlayerId) -> None:
    """The potion of life answers the night's attack, and nothing else (D-029).

    It is poured on the prey the pack settled on — possibly the witch herself,
    which is the only way she survives a night.
    """
    _ensure_the_potion_is_still_full(state, actor, RoleActionName.HEAL)

    taken = victim_seen_by_the_witch(state, policy=InformationPolicy())
    if taken is None or target != taken:
        raise IllegalIntentError("The potion of life only saves the victim of the night")


def _validate_poisoning(state: GameState, actor: PlayerId, target: PlayerId) -> None:
    """The potion of death takes any other living player (D-029)."""
    _ensure_the_potion_is_still_full(state, actor, RoleActionName.POISON)
    if target == actor:
        raise IllegalIntentError(f"Player {actor} would not poison themselves")

    _ensure_alive_target(state, target)


def _ensure_the_potion_is_still_full(
    state: GameState, actor: PlayerId, potion: RoleActionName
) -> None:
    """One potion a night, and each one works once in a whole game (D-029)."""
    if state.has_acted_tonight(actor):
        raise IllegalIntentError(f"Player {actor} has already used a potion tonight")
    if state.has_spent(actor, potion):
        raise IllegalIntentError(f"Player {actor} has no {potion} potion left")


def _validate_the_shot(state: GameState, actor: PlayerId, target: PlayerId) -> None:
    """The hunter takes one living player along, never himself (D-030)."""
    if actor not in {owed.id for owed in hunters_owing_a_shot(state)}:
        raise IllegalIntentError(f"Player {actor} has no shot to fire")
    if target == actor:
        raise IllegalIntentError(f"Player {actor} does not shoot themselves")

    _ensure_alive_target(state, target)


def _validate_priority_share(state: GameState, actor: PlayerId, intent: SharePriority) -> None:
    """Check one wolf's spread of the night's budget (D-008)."""
    if state.phase is not Phase.NIGHT:
        raise IllegalIntentError("The pack only designates its prey at night")
    _ensure_the_role_owns_the_action(state, actor, RoleActionName.DEVOUR)

    if state.has_acted_tonight(actor):
        raise IllegalIntentError(f"Player {actor} has already spread their points tonight")
    if intent.spent > PRIORITY_BUDGET:
        raise IllegalIntentError(
            f"A wolf spreads at most {PRIORITY_BUDGET} points, and this one spreads {intent.spent}"
        )

    named = [allocation.target for allocation in intent.allocations]
    if len(named) != len(set(named)):
        raise IllegalIntentError("A wolf may not put points on the same prey twice")

    _ensure_every_target_is_prey(state, named)


def _ensure_every_target_is_prey(state: GameState, named: list[PlayerId]) -> None:
    """The pack may only weigh prey it could actually take tonight.

    Read from the same place the view reads it, so the offer and the acceptance
    cannot describe different tables.
    """
    huntable = {player.id for player in prey_of(state)}

    for target in named:
        _ensure_alive_target(state, target)
        if target not in huntable:
            raise IllegalIntentError(f"Player {target} is not prey the pack may take tonight")
