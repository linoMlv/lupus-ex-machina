"""Who a game is projected for (D-100, D-105).

Derived from the state and nothing else. Mode, seat and the rule about the dead
all travel in the rules the state carries (J6), which is the same argument that
put them there: a recipient built from something only the caller knows would
show a client facts the journal never meant for them.

**A client never asks for one.** The spectator is omniscient, so a mode chosen
per request would let anybody open a second tab on a game they are playing — and
the critical leak test would stay green while protecting nothing at all.
"""

from lupus_ex_machina.engine.rules import GameMode
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.visibility import SPECTATOR, Recipient


def recipient_for(state: GameState) -> Recipient:
    """The recipient this game is projected for.

    The spectator watches a game they are not in, and so does a player whose
    character has died, when the rules allow it (D-105) — that one is decided by
    the game rather than asked for, which is what keeps D-100 intact.
    """
    table = state.rules.table
    if table.mode is GameMode.SPECTATOR or table.human_seat is None:
        return SPECTATOR

    human = next(player for player in state.players if player.seat == table.human_seat)
    if not state.player(human.id).alive and state.rules.information.reveal_everything_to_the_dead:
        return SPECTATOR
    return Recipient.of(human)
