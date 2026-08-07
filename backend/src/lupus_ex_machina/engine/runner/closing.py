"""How a phase is closed: resolve it, let the hunters fire, then look at victory.

The order is the rule (D-049, D-059). A shot fired after the count would settle
a game that was already over, and the reference scenarios of D-059 only come out
the way their author wrote them because the hunter goes first.
"""

from collections.abc import Callable

from lupus_ex_machina.engine.events import (
    EventPayload,
    GameEnded,
    PowerSpent,
    RoleRevealed,
    ShotFired,
)
from lupus_ex_machina.engine.hunter import hunters_owing_a_shot, someone_to_take_along
from lupus_ex_machina.engine.intents import Intent, RoleAction, Wait
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import RoleActionName
from lupus_ex_machina.engine.runner.scribe import Scribe
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.victory import Outcome, evaluate_victory

# What `resolve_day` and `resolve_night` both are: they close a phase, returning
# the new state and whoever died, if anyone.
Resolver = Callable[[GameState], tuple[GameState, tuple[PlayerId, ...]]]

# How a closed phase announces its outcome. Both resolutions produce the same
# shape — a victim or nobody — but they are two different facts of the game.
Announcement = Callable[[tuple[PlayerId, ...]], EventPayload]


async def close(
    scribe: Scribe, state: GameState, resolver: Resolver, announce: Announcement
) -> tuple[GameState, Outcome | None]:
    """Apply a resolution, then evaluate the victory — in that order (D-059)."""
    state = scribe.enter(state, Phase.RESOLUTION)
    state, victims = resolver(state)
    scribe.record(announce(victims), at=state)
    reveal_the_roles_of(scribe, state, victims)
    state = await _let_the_hunters_fire(scribe, state)

    outcome = evaluate_victory(state)
    if outcome is not None:
        state = scribe.enter(state, Phase.ENDED)
        scribe.record(GameEnded(outcome=outcome), at=state)
        return state, outcome
    return state, None


def reveal_the_roles_of(scribe: Scribe, state: GameState, victims: tuple[PlayerId, ...]) -> None:
    """Announce what the deceased were, when the configuration allows it (D-072).

    Death itself was already recorded, and is never configurable.
    """
    if not state.rules.information.reveal_role_on_death:
        return
    for victim in victims:
        scribe.record(RoleRevealed(player=victim, role=state.player(victim).role), at=state)


async def _let_the_hunters_fire(scribe: Scribe, state: GameState) -> GameState:
    """Fire every shot the round owes, before the victory is looked at (D-049).

    This is the one place a death happens in the middle of a phase, and the
    reason the whole thing is a loop: a hunter can take another hunter along.
    Each of them fires once, so it always ends.
    """
    while owed := hunters_owing_a_shot(state):
        hunter = owed[0]
        state = scribe.enter(state, Phase.AVENGING_SHOT)
        state = await _fire(scribe, state, hunter.id)
        state = scribe.enter(state, Phase.RESOLUTION)
    return state


async def _fire(scribe: Scribe, state: GameState, hunter: PlayerId) -> GameState:
    """Take the hunter's aim, or the engine's when he will not give one."""
    aimed = await _aim_of(scribe, state, hunter)
    state = state.with_power_spent_by(hunter, RoleActionName.SHOOT)
    scribe.record(PowerSpent(actor=hunter, action=RoleActionName.SHOOT), at=state)
    if aimed is None:
        return state

    target, chosen = aimed
    state = state.with_players_killed([target])
    scribe.record(ShotFired(hunter=hunter, target=target, chosen_by_the_hunter=chosen), at=state)
    reveal_the_roles_of(scribe, state, (target,))
    return state


async def _aim_of(
    scribe: Scribe, state: GameState, hunter: PlayerId
) -> tuple[PlayerId, bool] | None:
    """Whom the shot takes, and whether the hunter is the one who said so."""
    intent = await scribe.ask(state, hunter)
    if isinstance(intent, RoleAction) and scribe.accepts(state, hunter, intent):
        return intent.target, True

    _refuse_the_aim(scribe, state, hunter, intent)
    if not state.rules.roles.hunter_must_shoot:
        return None

    forced = someone_to_take_along(state, hunter)
    if forced is None:  # pragma: no cover - a game ends before a hunter is the last alive
        return None
    return forced, False


def _refuse_the_aim(scribe: Scribe, state: GameState, hunter: PlayerId, intent: Intent) -> None:
    """Count and record an intent handed in where only a shot was legal."""
    if isinstance(intent, Wait):
        return
    scribe.refuse(state, hunter, f"{intent.kind} is not a shot")
