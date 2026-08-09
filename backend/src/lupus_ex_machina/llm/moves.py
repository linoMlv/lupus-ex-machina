"""Turning what a model answered into the move the engine will be offered.

The second of the two translations a seat performs, and the one with all the
arithmetic in it: a view becomes a prompt on one side (:mod:`prompting`), an
answer becomes an intent here.

Nothing in here is clever, on purpose. What the model asked for is passed on as
it stands and the validator decides — an agent quietly correcting an illegal
move would be an agent making rules (D-001). The one liberty taken is with
*names*: a model only ever sees what is spoken at the table, so it answers with
names, and a name nobody bears is dropped rather than guessed at. Losing a whole
turn over one invented name would cost far more than the field is worth.
"""

from typing import assert_never

from lupus_ex_machina.engine.intents import (
    Intent,
    PriorityPoint,
    RoleAction,
    SharePriority,
    TakeTurn,
    Vote,
    Wait,
)
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.turn import (
    AddNote,
    DropNote,
    NotebookOperation,
    ReviseNote,
)
from lupus_ex_machina.engine.views import PlayerView
from lupus_ex_machina.llm.answers import TurnAnswer
from lupus_ex_machina.llm.speech import truncated
from lupus_ex_machina.llm.tagging import spoken


def intent_of(answered: TurnAnswer, view: PlayerView) -> Intent:
    """The move a turn amounts to, in the order the night and the day expect.

    A spread first, then a power, then a turn at the floor: they are the three
    shapes the phases offer, and a model that filled in two of them gets the one
    its phase can take. Whether it *may* is the validator's answer, not this
    one's (D-001).
    """
    if spread := _spread(answered, view):
        return spread
    if power := _power(answered, view):
        return power
    return _floor(answered, view) or Wait()


def notes_of(
    written: tuple[NotebookOperation, ...], view: PlayerView
) -> tuple[NotebookOperation, ...]:
    """The notebook operations, each cut to the words a note may hold (D-021)."""
    return tuple(_trimmed(operation, view.limits.notebook_words) for operation in written)


def named(view: PlayerView, name: str | None) -> PlayerId | None:
    """The player who goes by that name at this table, or nobody.

    Case and surrounding spaces are forgiven — a model writes "camille " often
    enough — but nothing else is guessed at: a name close to two players would
    make the engine pick for them.
    """
    if name is None:
        return None
    wanted = name.strip().casefold()
    return next(
        (player.id for player in view.players if player.name.casefold() == wanted),
        None,
    )


def _spread(answered: TurnAnswer, view: PlayerView) -> Intent | None:
    """The pack's allocation, dropping the prey nobody at the table is (D-008)."""
    allocations = tuple(
        PriorityPoint(target=found, points=share.points)
        for share in answered.priorities
        if (found := named(view, share.target)) is not None
    )
    return SharePriority(allocations=allocations) if allocations else None


def _power(answered: TurnAnswer, view: PlayerView) -> Intent | None:
    """The power a turn uses, when it names one and aims it at somebody real."""
    if answered.action is None or answered.target is None:
        return None
    target = named(view, answered.target)
    return RoleAction(action=answered.action, target=target) if target is not None else None


def _floor(answered: TurnAnswer, view: PlayerView) -> Intent | None:
    """Speaking, voting, or both — the three ways a turn at the floor goes (D-028)."""
    said = truncated(spoken(answered.speech or ""), view.limits.speech_words) or None
    voted = named(view, answered.vote) if answered.vote else None
    vote = Vote(target=voted) if voted is not None or answered.votes_blank else None

    if said is None and vote is None:
        return None
    return TakeTurn(
        speech=said,
        addressed=named(view, answered.addressed),
        accused=named(view, answered.accused),
        vote=vote,
    )


def _trimmed(operation: NotebookOperation, words: int) -> NotebookOperation:
    """The same operation, with its text cut to the words a note may hold.

    A deletion carries no text, which is exactly why it is its own type: there
    is nothing here to cut, and nothing to check for.
    """
    match operation:
        case AddNote() | ReviseNote():
            return operation.model_copy(update={"note": truncated(operation.note, words)})
        case DropNote():
            return operation
        case _:  # pragma: no cover - the union is closed, mypy proves this is dead
            assert_never(operation)
