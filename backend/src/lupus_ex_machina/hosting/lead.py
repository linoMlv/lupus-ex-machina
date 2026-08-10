"""How far ahead of its audience a game is allowed to run (D-014, D-023).

Two answers, and the difference between them is the whole of D-014.

A **watched** game may run a few turns ahead: a turn costs seconds of model
calls and half a minute of bubbles, so the display is what hides the latency —
provided the engine is allowed to be a little in front of it (D-023).

A **played** game runs one turn at a time. That is what makes "the pre-computed
turn is thrown away" unnecessary rather than merely hard: with a single turn in
flight, the button of an absolute priority is always read before the next turn
is played, so there is never a turn to throw — and no fact is ever removed from
a journal that does not allow removals (D-040).

*Settled with the project owner on 2026-08-11 (fiche J8, §8ter). The original
wording of J8.4.3 assumed a pre-generation living outside the journal, which
D-094 rules out by writing a turn down as it is played.*
"""

from lupus_ex_machina.configuration.schema import GameConfiguration
from lupus_ex_machina.engine.rules import GameMode

#: Turns a watched game may have played that nobody has caught up with. Two to
#: three is what hides the latency without paying for turns nobody may see.
WATCHING_LEAD = 3

#: Turns a played game may have in flight. One, and never less: a game allowed
#: none would never play its first turn, having no audience to wait for.
PLAYING_LEAD = 1


def turns_of_lead(configuration: GameConfiguration) -> int:
    """How many turns this game may play before its audience has caught up."""
    if configuration.rules.table.mode is GameMode.PLAYER:
        return PLAYING_LEAD
    return WATCHING_LEAD
