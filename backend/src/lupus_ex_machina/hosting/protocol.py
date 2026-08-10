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


class Broadcast(BaseModel):
    """One message: some facts, and the protocol they are written in."""

    model_config = ConfigDict(frozen=True)

    version: int = PROTOCOL_VERSION
    events: tuple[Event, ...] = Field(default_factory=tuple)
