"""What a player may still look up of rounds that are over (D-111).

Not a question of entitlement, and that is the whole of it. Everyone at the
table was allowed to see the count when it was read out; what this takes away is
the ability to **read it again**. So it does not belong in the projection, which
answers *who may know* (D-009) — it belongs on the way to whoever is about to
play, and it applies to a person exactly as to a model.

What the rule leaves standing is as deliberate as what it drops. The outcome of
a vote is a fact of the game, visible on the square: forgetting it would make
the state of play a lie. A blank vote is public the instant it is cast (D-027),
and hiding it later would reverse the asymmetry that decision wanted.

What it aims at: an agent that has to *remember* rather than look up, which
makes its notebook the only place the history of a vote survives — and gives a
real cost to not keeping one (D-005).
"""

from collections.abc import Sequence

from lupus_ex_machina.engine.events import BallotsRevealed, Event
from lupus_ex_machina.engine.rules import InformationOptions


def recollected(
    journal: Sequence[Event], *, day: int, information: InformationOptions
) -> tuple[Event, ...]:
    """That journal with the counts of past rounds dropped, if the rules say so.

    The count of the round **in progress** is untouched: it is a moment of play
    (D-082) and the staging is built on it (D-075). What goes is only what one
    would otherwise re-read a day later.
    """
    if information.public_vote_history:
        return tuple(journal)
    return tuple(
        event
        for event in journal
        if not (isinstance(event.payload, BallotsRevealed) and event.day < day)
    )
