"""Handing the facts of a running game to whoever is listening (D-094).

The observer of the journal notes a fact; this is what it notes into. It is
deliberately the dullest thing in the jalon: putting a fact on a queue cannot
block, cannot fail, and cannot make the engine wait on a client.

**One queue per listener.** Two clients read at their own pace, and a shared
queue would have the first reader take a fact the second never sees.

**Nothing here filters.** A broadcaster carries what was recorded; projection
happens at the edge, once per recipient, because that is where the recipient is
known (D-046).
"""

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager

from lupus_ex_machina.engine.events import Event
from lupus_ex_machina.hosting.protocol import Question, RateLimited

#: What a listener reads from. A fact of the game, a wait on the provider that
#: is playing it (D-066), a question the game has put to its person (D-096), or
#: ``None`` for "nothing more will come" — without the last one a client would
#: wait on a game that ended half an hour ago.
Told = Event | RateLimited | Question
Heard = asyncio.Queue[Told | None]


class Broadcaster:
    """Whoever is listening to a game, and how a fact reaches them."""

    def __init__(self) -> None:
        """Start with nobody listening."""
        self._listeners: list[Heard] = []
        self._closed = False

    def note(self, event: Event) -> None:
        """Hand that fact to every listener. Never waits, never refuses.

        This runs inside the task playing the game: an unbounded queue is what
        keeps a slow client from slowing the game down. What bounds the *game*
        is the buffer of J8.4, which pauses between turns rather than mid-fact.
        """
        self._tell(event)

    def _tell(self, told: Told | None) -> None:
        """Hand that to every listener. Never waits, never refuses."""
        for listener in self._listeners:
            listener.put_nowait(told)

    def close(self) -> None:
        """Tell every listener the game has nothing more to say.

        An end has to be sent, not inferred: a client with no way to know the
        game is over holds the line on one that ended half an hour ago.

        Said once however often it is asked. A game can reach its end *and* be
        given up — a task cancelled before it ever ran leaves no end behind it,
        so both paths close, and only one of them speaks.
        """
        if self._closed:
            return
        self._closed = True
        for listener in self._listeners:
            listener.put_nowait(None)

    def note_a_wait(self, seconds: float) -> None:
        """Tell every listener the provider is holding the game up (D-066).

        Announced rather than left to be inferred: a scene that stops with
        nothing on screen to explain it is the one thing D-066 asks not to do.
        """
        self._tell(RateLimited(seconds=seconds))

    def note_a_question(self, question: Question) -> None:
        """Tell every listener what the game is waiting on its person for (D-096).

        Put and closed alike travel this way. Announcing only the asking would
        leave a client sitting in front of a question the timer has since passed
        — which records no fact at all, so nothing else would ever say so.
        """
        self._tell(question)

    @contextmanager
    def listening(self) -> Iterator[Heard]:
        """Listen for as long as the block lasts, and stop being written to after.

        A queue left behind would go on filling for the rest of the game, for a
        client that hung up long ago.

        Somebody arriving after the end is told so at once: the end was said
        before they were listening, and a closed broadcast is closed for whoever
        comes next as well.
        """
        listener: Heard = asyncio.Queue()
        if self._closed:
            listener.put_nowait(None)
        self._listeners.append(listener)
        try:
            yield listener
        finally:
            self._listeners.remove(listener)
