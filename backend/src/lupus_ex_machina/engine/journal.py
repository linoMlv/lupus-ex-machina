"""The journal of a game, and what each recipient may read of it.

The journal is the source of truth (D-040): the state is derived from it, never
the other way round, which is what guarantees that no information can exist
without having been recorded — and therefore without an audience.

Append-only is meant literally. There is no way to remove, reorder or amend a
fact, because a retroactive correction would destroy the one property the whole
jalon rests on: replaying the journal gives back exactly the game that was
played. A mistake is fixed by recording another fact.

Filtering happens here, at the source, and not at the display: sending a whole
state to a client and hiding part of it on screen would leave everything
readable in the browser's development tools (D-046).
"""

from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from lupus_ex_machina.engine.events import Event, EventPayload
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.visibility import Recipient

#: Where the timestamp of a fact comes from. Injected so a game can be replayed
#: instant for instant, and so tests do not depend on the wall clock.
Clock = Callable[[], datetime]

#: Somebody told of each fact as it is written (D-094). Injected like the clock,
#: which is what lets a game in progress be watched without the engine knowing
#: that anybody is watching.
#:
#: **It notes, it does not emit.** This runs inside the task playing the game, so
#: an observer that reached a network would make the game wait on a client;
#: projecting and sending belong to whoever collects what it put aside.
Observer = Callable[[Event], None]


def utc_now() -> datetime:
    """Read the current instant, timezone-aware."""
    return datetime.now(UTC)


class Journal:
    """The facts of one game, in the order they happened."""

    def __init__(self, *, clock: Clock = utc_now, observer: Observer | None = None) -> None:
        """Start an empty journal, reading its timestamps from ``clock``.

        An observer, if there is one, is told of each fact as it is appended.
        """
        self._events: list[Event] = []
        self._clock = clock
        self._observer = observer

    def record(self, payload: EventPayload, *, at: GameState) -> Event:
        """Append a fact, stamped with the moment and the phase it happened in.

        The phase and day come from the state rather than from the caller: they
        describe *when* a fact happened, and a caller in a position to get that
        wrong is a caller that eventually will.
        """
        event = Event(
            sequence=len(self._events),
            recorded_at=self._clock(),
            phase=at.phase,
            day=at.day,
            payload=payload,
        )
        self._events.append(event)
        if self._observer is not None:
            self._observer(event)
        return event

    @property
    def events(self) -> tuple[Event, ...]:
        """Every fact recorded so far, as a snapshot nothing can be changed through."""
        return tuple(self._events)

    def __len__(self) -> int:
        """Number of facts recorded so far."""
        return len(self._events)


def project_journal(events: Iterable[Event], recipient: Recipient) -> tuple[Event, ...]:
    """Keep only the facts that recipient is entitled to.

    Sequence numbers are left untouched. Renumbering would look tidier and would
    be a leak: the gaps a recipient sees say nothing, whereas a dense run would
    tell them exactly how many facts were withheld.
    """
    return tuple(event for event in events if event.is_visible_to(recipient))
