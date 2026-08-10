"""What travels to a client, and how it says what it is (D-099).

The facts of the journal, projected, in an envelope that carries a version. One
model of data rather than two: the projection of J3 is reused as it stands, and
nothing here filters anything a second time — being tempted to would mean J3 is
incomplete.

The version is here from the first day on purpose. The front end moves on its
own from J9, and a protocol that changed shape without saying so is the kind of
mismatch that takes an afternoon to diagnose.
"""

from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.engine.events import Event

#: Version of what a client is sent. Bumped whenever the shape below changes in
#: a way an older front end could not read.
PROTOCOL_VERSION = 1

#: What a client declares when it has never heard anything.
NOTHING_HEARD = -1

#: What a client sends back to say how far it has *displayed* — not merely
#: received. It is what lets the game go on: it runs a few turns ahead of the
#: display and waits once too many are in flight (D-023, J8.4).
SHOWN = "shown"


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
