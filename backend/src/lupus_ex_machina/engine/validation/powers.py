"""What a role may play, on whom, and when.

The registry says which powers a role owns (D-010); this says whether the one
being played is legal right now. Read from the registry rather than restated, so
the declaration and the rule that enforces it cannot drift apart.
"""

from typing import assert_never

from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.hunter import hunters_owing_a_shot
from lupus_ex_machina.engine.intents import RoleAction, SharePriority
from lupus_ex_machina.engine.night import prey_of, victim_seen_by_the_witch
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import ROLES, RoleActionName
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation.actor import ensure_alive_target


def validate_role_action(state: GameState, actor: PlayerId, intent: RoleAction) -> None:
    """Judge a single-target power: whose it is, when it is played, and on whom."""
    ensure_the_role_owns_the_action(state, actor, intent.action)
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


def ensure_the_role_owns_the_action(
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

    ensure_alive_target(state, target)


def _validate_healing(state: GameState, actor: PlayerId, target: PlayerId) -> None:
    """The potion of life answers the night's attack, and nothing else (D-029).

    It is poured on the prey the pack settled on — possibly the witch herself,
    which is the only way she survives a night, and the one part of this a table
    may switch off.
    """
    _ensure_the_potion_is_still_full(state, actor, RoleActionName.HEAL)
    if target == actor and not state.rules.roles.witch_may_save_herself:
        raise IllegalIntentError(f"Player {actor} may not pour the potion of life on themselves")

    taken = victim_seen_by_the_witch(state)
    if taken is None or target != taken:
        raise IllegalIntentError("The potion of life only saves the victim of the night")


def _validate_poisoning(state: GameState, actor: PlayerId, target: PlayerId) -> None:
    """The potion of death takes any other living player (D-029)."""
    _ensure_the_potion_is_still_full(state, actor, RoleActionName.POISON)
    if target == actor:
        raise IllegalIntentError(f"Player {actor} would not poison themselves")

    ensure_alive_target(state, target)


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

    ensure_alive_target(state, target)


def validate_priority_share(state: GameState, actor: PlayerId, intent: SharePriority) -> None:
    """Check one wolf's spread of the night's budget (D-008)."""
    if state.phase is not Phase.NIGHT:
        raise IllegalIntentError("The pack only designates its prey at night")
    ensure_the_role_owns_the_action(state, actor, RoleActionName.DEVOUR)

    if state.has_acted_tonight(actor):
        raise IllegalIntentError(f"Player {actor} has already spread their points tonight")
    budget = state.rules.night.priority_budget
    if intent.spent > budget:
        raise IllegalIntentError(
            f"A wolf spreads at most {budget} points, and this one spreads {intent.spent}"
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
        ensure_alive_target(state, target)
        if target not in huntable:
            raise IllegalIntentError(f"Player {target} is not prey the pack may take tonight")
