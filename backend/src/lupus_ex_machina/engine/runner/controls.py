"""The two hands that reach into a running debate from outside the rules.

Both are mutable and both are read *between* turns, never inside one. That is
where "the floor is never cut in the middle of a turn" comes from (D-014): no
rule says it, the place these are read does.
"""

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
