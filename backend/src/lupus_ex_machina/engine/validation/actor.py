"""Whether this player may act at all, and whether that target can be aimed at.

Asked before anything else, of every intent. The rest of the validation is about
the move; this is about the two players it involves.
"""

from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.hunter import hunters_owing_a_shot
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.state import GameState

ACTIONABLE_PHASES = frozenset({Phase.NIGHT_ZERO, Phase.DAY, Phase.NIGHT, Phase.AVENGING_SHOT})


def ensure_actor_may_act(state: GameState, actor: PlayerId) -> None:
    """Only the living act — with one exception, and it is the whole point of it.

    A hunter fires as he dies (D-030). His shot is the single move the rules
    accept from a dead player, and it is accepted nowhere but in its own phase.
    """
    ensure_known(state, actor)
    if state.phase not in ACTIONABLE_PHASES:
        raise IllegalIntentError(f"No intent is accepted during phase {state.phase}")
    if not state.is_alive(actor) and actor not in {owed.id for owed in hunters_owing_a_shot(state)}:
        raise IllegalIntentError(f"Player {actor} is dead and cannot act")


def ensure_known(state: GameState, player: PlayerId) -> None:
    """Refuse a player this game never dealt a seat to."""
    if not state.has_player(player):
        raise IllegalIntentError(f"Unknown player {player}")


def ensure_alive_target(state: GameState, target: PlayerId) -> None:
    """Refuse a target who is unknown, or already dead."""
    ensure_known(state, target)
    if not state.is_alive(target):
        raise IllegalIntentError(f"Player {target} is dead and cannot be targeted")
