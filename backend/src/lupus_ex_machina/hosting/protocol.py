"""What travels to a client, and how it says what it is (D-099).

The facts of the journal, projected, in an envelope that carries a version. One
model of data rather than two: the projection of J3 is reused as it stands, and
nothing here filters anything a second time — being tempted to would mean J3 is
incomplete.

The version is here from the first day on purpose. The front end moves on its
own from J9, and a protocol that changed shape without saying so is the kind of
mismatch that takes an afternoon to diagnose.
"""

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.engine.events import Event
from lupus_ex_machina.engine.views import PlayerView

#: Version of what a client is sent. Bumped whenever the shape below changes in
#: a way an older front end could not read.
PROTOCOL_VERSION = 1

#: What a client declares when it has never heard anything.
NOTHING_HEARD = -1

#: What a client sends back to say how far it has *displayed* — not merely
#: received. It is what lets the game go on: it runs a few turns ahead of the
#: display and waits once too many are in flight (D-023, J8.4).
SHOWN = "shown"

#: What a client sends back to answer a question put to its player (D-096). The
#: only other thing that ever travels upward: the buttons and the moderator's
#: hand are routes, because they outlive a connection (D-109).
ANSWER = "answer"


class AskedFor(StrEnum):
    """What the game is waiting on its person for (D-096).

    The two moments an agent is ever asked anything with a decision in it: the
    turn it plays, and the stock it takes of a round that has closed (D-086).
    Bidding is not among them — a person's bid is read off a button rather than
    waited for, or the game would stop between every turn at the floor (D-107).
    """

    TURN = "turn"
    REFLECTION = "reflection"


class QuestionState(StrEnum):
    """Whether a question is still waiting on an answer."""

    PUT = "put"
    CLOSED = "closed"


class QuestionPut(BaseModel):
    """A question the game has put to its person, and is waiting on.

    It carries the **view**, which is what says what may be done right now:
    legality lives with the validator and nowhere else (D-001), so a client left
    to work it out would be a second copy of the rules. That view is the very
    one an agent is handed, filtered by the projection of J3 — handing it to the
    person playing the seat widens nothing (GL-3).
    """

    model_config = ConfigDict(frozen=True)

    state: Literal[QuestionState.PUT] = QuestionState.PUT
    number: int
    """Which question this is. An answer names it, so an answer to the question
    before — from a tab that was slow, or one that came back — cannot be taken
    for an answer to this one."""
    asked_for: AskedFor
    view: PlayerView


class QuestionClosed(BaseModel):
    """A question that is no longer waiting: answered, or passed by the timer.

    Said rather than inferred, for the reason an end of stream is said: a turn
    the timer passed records **nothing at all** (D-097, and `Wait` leaves the
    state untouched), so a client with only the facts to go on would sit for
    ever in front of a question the game stopped asking.
    """

    model_config = ConfigDict(frozen=True)

    state: Literal[QuestionState.CLOSED] = QuestionState.CLOSED
    number: int


#: A question put, or the same question closed. A union rather than one type
#: with optional fields, like every other closed set on this project (D-035): a
#: closing carries no view and no subject, so the two shapes are two types.
Question = Annotated[QuestionPut | QuestionClosed, Field(discriminator="state")]


class Answer(BaseModel):
    """What a client sends back to a question put to its player.

    The payload is left untyped here on purpose: the **question decides its
    shape**, and the question is the server's own. Declaring it as a turn or a
    stock-taking would put the choice in the client's hands — and since a turn
    *is* a stock-taking with a move on it, one offered where the other was asked
    for could be taken with its move quietly dropped.
    """

    model_config = ConfigDict(frozen=True)

    number: int
    """Which question is being answered. An answer to the question before — from
    a tab that was slow, or one that came back — must not be taken for this one."""
    answered: dict[str, Any]


class RateLimited(BaseModel):
    """The provider is refusing for rate reasons, and the game is waiting (D-066).

    Not a fact of the journal: it says nothing about the game, only about what
    it is being played through, so it never gets a sequence and never reaches a
    replay. It travels beside the facts rather than among them.
    """

    model_config = ConfigDict(frozen=True)

    seconds: float


class Broadcast(BaseModel):
    """One message: what happened, or what is being waited for.

    Both in one envelope rather than two kinds of message: it describes the
    state of the stream at an instant, and a wait is part of that state. A front
    end that sees `waiting` puts up an indicator (D-066) instead of showing a
    scene that has stopped for no stated reason.
    """

    model_config = ConfigDict(frozen=True)

    version: int = PROTOCOL_VERSION
    events: tuple[Event, ...] = Field(default_factory=tuple)
    waiting: float | None = None
    question: Question | None = None
    """What the game is waiting on its player for, or that it no longer is
    (D-096). Part of the same envelope for the same reason a wait is: it
    describes the state of the stream at an instant, and being asked something
    is part of that state."""
