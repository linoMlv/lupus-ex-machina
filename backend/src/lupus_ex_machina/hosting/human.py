"""The one seat a person plays, and how a game waits on them (D-096).

An agent, like every other. The engine asks it the same three questions it asks
a model and never learns which it is talking to, so neither the legality of a
move nor the tightness of the information has a special case to carry (D-001).
What changes is only where the answer comes from.

The three questions are not waited on alike, and that is the whole design here.

**A bid is read, never waited for** (D-107). The floor is auctioned after every
turn, some twenty-five times a day of play: waiting on a person each time would
have them answer twenty-five times over just to say they have nothing to add,
and would stop the game between every turn. So the button of `demander la
parole` is what bids, and it bids at once.

**A turn and a stock-taking are waited for**, indefinitely by default (D-097,
D-108). A game that does not progress is an admitted state (D-078), and the
moderator's hand is the way out of it. A timer may be set, and passes the turn
when it runs out.
"""

import asyncio
from collections.abc import Callable, Sequence

from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.events import Event
from lupus_ex_machina.engine.intents import Wait
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.turn import Reflection, Turn
from lupus_ex_machina.engine.views import PlayerView
from lupus_ex_machina.hosting.protocol import AskedFor, Question, QuestionClosed, QuestionPut

#: How a question is announced to whoever is watching. Injected rather than
#: reached for, like the observer a journal takes (D-094): the agent says what
#: it is waiting on and never learns who, if anyone, is listening.
Announce = Callable[[Question], None]

#: What a bid is worth once the button has been pressed, and while it has not.
#: The two ends of the scale rather than middling values: a person asking for
#: the floor wants it as much as anyone can, and one who has not asked is not in
#: the auction at all. The arbitration still applies — recency and quota weigh
#: on a person exactly as on a model, which is what separates *asking* for the
#: floor from *taking* it (D-014).
WANTS_THE_FLOOR, WANTS_NOTHING = 100, 0

#: What the auction is told the person would say. A bid has to carry an
#: intention, and this one is never recorded: an auction keeps the scores.
ASKING_TO_SPEAK = "Je demande la parole."
SAYING_NOTHING = "Je n'ai rien à ajouter."


class HumanAgent:
    """One seat, played by a person."""

    def __init__(
        self, player: PlayerId, *, announce: Announce, timeout: float | None = None
    ) -> None:
        """Take which seat this is, who to tell, and how long a question stands.

        No timeout is the default, and it means the game waits for as long as it
        takes (D-097).
        """
        self._player = player
        self._announce = announce
        self._timeout = timeout
        self._wants_the_floor = False
        self._asked = 0
        self._question: QuestionPut | None = None
        self._answer: asyncio.Future[Reflection] | None = None

    @property
    def player(self) -> PlayerId:
        """The seat this person plays."""
        return self._player

    @property
    def question(self) -> QuestionPut | None:
        """What the game is waiting on them for, if anything.

        Readable rather than only announced, so a client that connects while a
        question is standing is told about it. Announced alone, a question put
        before somebody opened their browser would never reach them, and the
        game would wait on an answer nobody knew was owed (D-102).
        """
        return self._question

    # --- What the person does --------------------------------------------

    def request_the_floor(self) -> None:
        """Ask for the floor, to be weighed against everybody else's wish for it.

        It stays asked until the floor is actually won. Spent on the next
        auction instead, a request lost to somebody else's better bid would
        evaporate, and the person would have to press again after every turn.
        """
        self._wants_the_floor = True

    def answer(self, number: int, answered: Reflection) -> bool:
        """Take the person's answer to the question that number names.

        The first answer to a question wins and the others are refused. Several
        connections may share the one identity of a played game, so without this
        two tabs would play two moves for the same turn.

        An answer of the wrong shape is refused rather than half-taken: a turn
        offered where a stock-taking was asked for would have its move silently
        dropped, since a turn *is* a reflection with a move on it.
        """
        question, waiting = self._question, self._answer
        if question is None or waiting is None or waiting.done():
            return False
        if question.number != number:
            return False
        if isinstance(answered, Turn) is not (question.asked_for is AskedFor.TURN):
            return False

        waiting.set_result(answered)
        return True

    # --- What the engine asks --------------------------------------------

    async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
        """Say whether the person has asked for the floor. Never waits (D-107)."""
        asking = self._wants_the_floor
        return Bid(
            urgency=WANTS_THE_FLOOR if asking else WANTS_NOTHING,
            intention=ASKING_TO_SPEAK if asking else SAYING_NOTHING,
        )

    async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
        """Put the turn to the person and wait for it (D-096).

        A turn they may speak in is the floor they asked for, so the request is
        spent here — the one place where asking for the floor and getting it are
        known to be the same event.
        """
        if view.may_speak:
            self._wants_the_floor = False

        answered = await self._put(AskedFor.TURN, view)
        # A turn is only ever answered with a turn, `answer` refusing any other
        # shape. What this narrows is the silence the timer hands back, and that
        # silence does nothing at all — never a blank vote, which would close
        # the floor and could not be taken back (D-097).
        return answered if isinstance(answered, Turn) else Turn(intent=Wait())

    async def reflect(self, view: PlayerView, journal: Sequence[Event]) -> Reflection:
        """Put the round that just closed to the person, and wait (D-086, D-108)."""
        answered = await self._put(AskedFor.REFLECTION, view)
        return answered if answered is not None else Reflection()

    async def _put(self, asked_for: AskedFor, view: PlayerView) -> Reflection | None:
        """Ask, wait, and hand back the answer — or nothing, when time ran out.

        The question is cleared however the wait ends, a cancelled game
        included: one left standing would have a client answering a question the
        game stopped asking.
        """
        self._asked += 1
        put = QuestionPut(number=self._asked, asked_for=asked_for, view=view)
        self._question = put
        self._answer = asyncio.get_running_loop().create_future()
        self._announce(put)
        try:
            return await asyncio.wait_for(self._answer, self._timeout)
        except TimeoutError:
            return None
        finally:
            self._question, self._answer = None, None
            self._announce(QuestionClosed(number=put.number))
