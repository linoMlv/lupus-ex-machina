"""A player's notebook, rebuilt from the facts they wrote (D-005, D-088).

The notebook is not kept anywhere. It is replayed from the journal, like the
state itself (D-040), and that is what makes it survive a reconnection and a
replay — an agent holding its own notes would lose them the moment it was
handed a new game to continue.

It also gives the history for free: the facts keep every revision, so the
spectator can watch a belief change rather than only see what it ended up as.
"""

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.engine.events import (
    Event,
    NotebookEntryDropped,
    NotebookEntryRecorded,
)
from lupus_ex_machina.engine.players import PlayerId


class Note(BaseModel):
    """One line of a notebook, and the number its author refers to it by."""

    model_config = ConfigDict(frozen=True)

    entry: int = Field(ge=0)
    note: str = Field(min_length=1)


def notebook_of(events: Iterable[Event], player: PlayerId) -> tuple[Note, ...]:
    """The notebook that player's own facts leave behind, in numbered order.

    Facts of other players are skipped rather than trusted to be absent: this is
    read from a journal that may or may not have been projected, and a notebook
    that changed depending on which one it was given would be a trap.
    """
    written: dict[int, str] = {}
    for event in events:
        match event.payload:
            case NotebookEntryRecorded(player=author, entry=entry, note=note) if author == player:
                written[entry] = note
            case NotebookEntryDropped(player=author, entry=entry) if author == player:
                written.pop(entry, None)
            case _:
                continue

    return tuple(Note(entry=entry, note=note) for entry, note in sorted(written.items()))


def next_entry_for(events: Iterable[Event], player: PlayerId) -> int:
    """The number the next note of that player will carry.

    Counted from every note ever written rather than from the notebook as it
    stands: a number freed by a deletion is never handed out again, so a note
    the agent remembers by its number cannot come back as another one.
    """
    return sum(
        1
        for event in events
        if isinstance(event.payload, NotebookEntryRecorded)
        and event.payload.player == player
        and not event.payload.revised
    )
