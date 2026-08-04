"""The shot a hunter fires as he dies (D-030, D-049, D-055).

Two rules put this in a module of its own rather than inside a resolution.

The shot is **always fired by day and in front of everyone**, even when the night
was what killed him — in which case it happens before the debate opens. It is
therefore a phase, something played and watched, not an effect applied wherever
the death occurred.

It is resolved **before the victory is evaluated** (D-049). That single ordering
is what makes the reference scenario come out the way its author says it does: a
lone wolf that eats the hunter loses to the shot that answers, and the village
takes the game.
"""

from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import ROLES, DeathTrigger, RoleActionName
from lupus_ex_machina.engine.state import GameState


def hunters_owing_a_shot(state: GameState) -> tuple[Player, ...]:
    """The dead who still take someone along, in seat order.

    Owing a shot is read from the death trigger the role declares (D-010) and
    from whether it has already been spent — which is also what stops two
    hunters shooting each other in circles.
    """
    return tuple(
        sorted(
            (
                player
                for player in state.players
                if not player.alive
                and ROLES[player.role].on_death is DeathTrigger.AVENGING_SHOT
                and not state.has_spent(player.id, RoleActionName.SHOOT)
            ),
            key=lambda player: player.seat,
        )
    )


def someone_to_take_along(state: GameState, hunter: PlayerId) -> PlayerId | None:
    """Whom the engine fires at when the hunter will not (D-055).

    Non-renounceable is taken literally: a rule the agents could quietly opt out
    of would not be a rule. The choice falls on the lowest seat still standing,
    which is arbitrary but the same on every run, so a game replays identically
    (D-040).
    """
    standing = [player for player in state.living if player.id != hunter]
    if not standing:
        return None

    return min(standing, key=lambda player: player.seat).id
