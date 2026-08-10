"""The three hands that reach into a running game from outside the rules.

All three are read *between* turns, never inside one. That is where "the floor
is never cut in the middle of a turn" comes from (D-014): no rule says it, the
place these are read does — and the pause of :class:`Pacing` inherits the same
property for free.
"""

import asyncio

from lupus_ex_machina.engine.players import PlayerId


class DebateControl:
    """The moderator's hand on how long a debate may run (D-048).

    Mutable, and consulted before every turn, because it is a control the user
    works during the game rather than a setting chosen before it: J11 wires the
    button to :meth:`cut_to`. Left alone, it never shortens anything.
    """

    def __init__(self, turns_left: int | None = None) -> None:
        """Take how many turns the debate may still have, or ``None`` for no limit."""
        self._turns_left = turns_left

    @property
    def turns_left(self) -> int | None:
        """Turns the debate may still have, ``None`` when the user has not said."""
        return self._turns_left

    def cut_to(self, turns: int) -> None:
        """Allow the debate that many more turns. Zero calls the vote at once."""
        self._turns_left = turns

    def spend_a_turn(self) -> None:
        """Count one turn against the allowance, if there is one."""
        if self._turns_left is not None:
            self._turns_left -= 1

    @property
    def is_out_of_turns(self) -> bool:
        """Whether the moderator has called time on the debate."""
        return self._turns_left is not None and self._turns_left <= 0


class FloorClaim:
    """The human player's claim on the next turn at the floor (D-014).

    Absolute priority, and it wins nothing: the claim is honoured instead of an
    auction rather than inside one. It is read *between* turns, which is the
    whole of "at the end of the turn under way, never inside it" — a turn is
    played to its end before the claim is looked at again.

    Spent once honoured, otherwise pressing the button would hand its owner the
    floor for the rest of the day. Mutable and read late, like DebateControl,
    because it is a button the user presses during the game (J11).
    """

    def __init__(self) -> None:
        """Start with nobody claiming anything."""
        self._claimed_by: PlayerId | None = None

    def claim(self, player: PlayerId) -> None:
        """Claim the next turn at the floor for that player."""
        self._claimed_by = player

    def take(self) -> PlayerId | None:
        """Hand back whoever claimed the floor, and forget the claim."""
        claimed, self._claimed_by = self._claimed_by, None
        return claimed


class Pacing:
    """How far ahead of its audience a game may run (D-023, D-095).

    The engine plays far faster than anybody watches — a turn costs seconds of
    model calls and half a minute of bubbles — so left alone it would play a
    whole game into a buffer nobody has looked at, spending the call budget on
    turns the user may never see.

    A turn is *in flight* until whoever is watching says they have shown
    everything that existed when it began. Past a few of those, the game waits.

    **Nobody is watching by default.** A scripted game, `make play`, the suite:
    none of them has an audience, and a game that paused for one would never
    finish. Only a hosted game hands out a paced one.
    """

    def __init__(self, turns_in_flight: int | None = None) -> None:
        """Take how many turns may go unshown, or ``None`` to never wait."""
        self._limit = turns_in_flight
        self._unshown: list[int] = []
        self._room = asyncio.Event()

    @property
    def turns_in_flight(self) -> int:
        """How many turns have been played that nobody has caught up with."""
        return len(self._unshown)

    async def before_a_turn(self, *, recorded: int) -> None:
        """Wait until there is room for one more turn, then count it in flight.

        What a turn is marked with is the last fact that existed *before* it —
        so it stops being in flight the moment the audience reaches its opening.
        The very first turn of a game is marked with nothing, and can never wait
        for an audience that has had nothing to look at yet.
        """
        while self._limit is not None and len(self._unshown) >= self._limit:
            self._room.clear()
            await self._room.wait()
        self._unshown.append(recorded - 1)

    def shown(self, sequence: int) -> None:
        """Take note that everything up to that fact has been shown."""
        self._unshown = [mark for mark in self._unshown if mark > sequence]
        self._room.set()
