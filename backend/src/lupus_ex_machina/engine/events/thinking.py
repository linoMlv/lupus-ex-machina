"""What a player kept to themselves: their reasoning, their notebook, their misses.

Thought never crosses into speech, and that is held by the code rather than by a
prompt (D-004, GL-3). These facts are their author's own, and the spectator's —
seeing them is what the spectator mode is for.
"""

from typing import Literal

from pydantic import Field

from lupus_ex_machina.engine.events.fact import EventKind, Fact
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.visibility import Visibility


class PrivateReasoningRecorded(Fact):
    """What a player thought before acting, which nobody at the table hears (D-004).

    The guarantee it carries belongs to the information model, not to the
    agents: thought never crosses into speech, and that is held by the code
    rather than by a prompt (GL-3).
    """

    kind: Literal[EventKind.PRIVATE_REASONING_RECORDED] = EventKind.PRIVATE_REASONING_RECORDED
    player: PlayerId
    reasoning: str

    @property
    def audience(self) -> Visibility:
        """Its author, and the spectator watching over their shoulder."""
        return Visibility.for_player(self.player)


class NotebookEntryRecorded(Fact):
    """A line a player put in their own notebook, new or rewritten (D-005).

    The operation travels with the line, because the notebook is rebuilt by
    replaying these facts rather than stored anywhere (D-088). Adding and
    revising are one fact and deleting is another: a deletion carries no text,
    and one type covering both would have to make the text optional — which
    every reader would then have to handle, forever.
    """

    kind: Literal[EventKind.NOTEBOOK_ENTRY_RECORDED] = EventKind.NOTEBOOK_ENTRY_RECORDED
    player: PlayerId
    entry: int = Field(ge=0)
    note: str = Field(min_length=1)
    revised: bool = False
    """False for a new note, true for one written over an older one.

    Kept because the history is the point (D-005): the spectator watches a
    belief change, and a revision that looked like a first thought would hide
    exactly what is interesting.
    """

    @property
    def audience(self) -> Visibility:
        """Its author, and the spectator."""
        return Visibility.for_player(self.player)


class NotebookEntryDropped(Fact):
    """A line a player struck out of their own notebook (D-005)."""

    kind: Literal[EventKind.NOTEBOOK_ENTRY_DROPPED] = EventKind.NOTEBOOK_ENTRY_DROPPED
    player: PlayerId
    entry: int = Field(ge=0)

    @property
    def audience(self) -> Visibility:
        """Its author, and the spectator."""
        return Visibility.for_player(self.player)


class IntentRejected(Fact):
    """An agent asked for something the rules refuse.

    Kept because it is the raw material for judging how models behave (J7): a
    game where every second intent is refused is a prompt problem, and nothing
    else would show it.
    """

    kind: Literal[EventKind.INTENT_REJECTED] = EventKind.INTENT_REJECTED
    actor: PlayerId
    reason: str

    @property
    def audience(self) -> Visibility:
        """The spectator alone: the table never learns that someone fumbled."""
        return Visibility.spectator_only()
