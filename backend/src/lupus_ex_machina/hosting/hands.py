"""What reaches into a running game from outside its rules (J8.5, D-109).

The engine already groups these three, and for the reason that matters here:
all of them are read *between* turns, never inside one. That is where "the floor
is never cut in the middle of a turn" comes from (D-014) — no rule says it, the
place they are read does.

What this adds is who may work them. **Calling time on a debate is the
moderator's** and works whether or not anybody sits at the table (D-048).
**Taking or asking for the floor is the person's**, and a watched game has
neither. Refusing rather than passing over is deliberate: a button that answers
and does nothing is the hardest kind of fault to see from a screen.

None of them travels on the websocket. They outlive a connection, and the
moderator's works in a mode that has no upward channel at all (D-109).
"""

from lupus_ex_machina.configuration.schema import GameConfiguration
from lupus_ex_machina.engine.runner.controls import DebateControl, FloorClaim, Pacing
from lupus_ex_machina.hosting.errors import NobodyIsPlayingError
from lupus_ex_machina.hosting.human import HumanAgent
from lupus_ex_machina.hosting.lead import turns_of_lead

NOBODY_AT_THE_TABLE = "Personne n'occupe de siège dans cette partie."


class Hands:
    """The controls of one game, and the person they may belong to."""

    def __init__(self, configuration: GameConfiguration, person: HumanAgent | None) -> None:
        """Build the three controls this game will be played under.

        Held rather than left to `play_game` to default: built there, they would
        exist inside the task playing the game and nothing outside could ever
        reach one — which is exactly what was true before J8.5.
        """
        self._person = person
        self.pacing = Pacing(turns_in_flight=turns_of_lead(configuration))
        self.claim = FloorClaim()
        self.control = DebateControl(configuration.rules.vote.turns_before_forced_vote)

    @property
    def debate_turns_left(self) -> int | None:
        """Turns the debate may still have, ``None`` when nothing limits it."""
        return self.control.turns_left

    def claim_the_floor(self) -> None:
        """Take the next turn at the floor for the person, outright (D-014).

        Absolute priority, and it wins nothing: the claim is honoured *instead
        of* an auction rather than inside one, so the turn under way is played to
        its end before it is looked at.
        """
        self.claim.claim(self._someone().player)

    def request_the_floor(self) -> None:
        """Ask for the floor, to be weighed against everybody else's wish for it.

        The other button, and the difference is the whole of D-014: this one
        goes into the auction and is scored there like any bid (D-107).
        """
        self._someone().request_the_floor()

    def cut_the_debate_to(self, turns: int) -> None:
        """Allow the debate that many more turns. Zero calls the vote at once (D-048)."""
        self.control.cut_to(turns)

    def shown(self, sequence: int) -> None:
        """Take note that a client has displayed everything up to that fact.

        This is what lets the game go on: it runs a few turns ahead of whoever
        is watching (D-023) and waits once too many are in flight — one single
        turn when somebody is *playing*, so an absolute priority is always read
        before the next turn (D-014).
        """
        self.pacing.shown(sequence)

    def _someone(self) -> HumanAgent:
        """The person at the table, or a plain refusal that there is one."""
        if self._person is None:
            raise NobodyIsPlayingError(NOBODY_AT_THE_TABLE)
        return self._person
