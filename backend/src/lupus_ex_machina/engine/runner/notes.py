"""One operation on a notebook, turned into the fact that will replay it (D-088).

A notebook is not stored anywhere: it is rebuilt by replaying its author's own
facts, which is why the operation — and not the resulting page — is what gets
written down (D-005, D-040).
"""

from typing import assert_never

from lupus_ex_machina.engine.events import (
    Event,
    EventPayload,
    NotebookEntryDropped,
    NotebookEntryRecorded,
)
from lupus_ex_machina.engine.notebook import next_entry_for, notebook_of, refusal_for
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.turn import AddNote, DropNote, NotebookOperation, ReviseNote


def refusal_of(
    operation: NotebookOperation,
    events: tuple[Event, ...],
    player: PlayerId,
    *,
    cap: int,
) -> str | None:
    """Why that operation cannot be written, or ``None`` when it can (D-005).

    Judged against the notebook as the previous operations of the same turn left
    it, so an agent cannot get past the cap by writing everything at once.
    """
    return refusal_for(operation, notebook_of(events, player), cap=cap)


def fact_of(
    operation: NotebookOperation, events: tuple[Event, ...], player: PlayerId
) -> EventPayload:
    """Turn one operation into the fact that will replay it (D-088).

    A new note is numbered here rather than by its author: the number is how a
    later turn refers back to it, so it has to come from the one place that knows
    every note ever written.
    """
    match operation:
        case AddNote():
            return NotebookEntryRecorded(
                player=player, entry=next_entry_for(events, player), note=operation.note
            )
        case ReviseNote():
            return NotebookEntryRecorded(
                player=player, entry=operation.entry, note=operation.note, revised=True
            )
        case DropNote():
            return NotebookEntryDropped(player=player, entry=operation.entry)
        case _:  # pragma: no cover - the union is closed, mypy proves this is dead
            assert_never(operation)
