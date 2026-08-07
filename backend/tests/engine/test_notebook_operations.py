"""What an operation on a notebook says, and how it replays (D-005, D-088)."""

from collections.abc import Sequence

import pytest
from pydantic import TypeAdapter, ValidationError

from lupus_ex_machina.agents.scripted import Scripted, SilentAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.events import (
    Event,
)
from lupus_ex_machina.engine.journal import project_journal
from lupus_ex_machina.engine.notebook import notebook_of
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.runner import GameResult, play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.turn import (
    AddNote,
    DropNote,
    NotebookOperation,
    NotebookOperationName,
    ReviseNote,
    Turn,
)
from lupus_ex_machina.engine.views import PlayerView
from lupus_ex_machina.engine.visibility import Recipient
from support.thinkers import (
    FIRST_NOTE,
    FORCED_DESIGNATION,
    NOTE,
    REVISED_NOTE,
    SECOND_NOTE,
)

# --- What an operation on the notebook has to say (D-005) --------------------


@pytest.mark.parametrize(
    "written",
    [
        {"operation": "add"},
        {"operation": "revise", "entry": 0},
        {"operation": "revise", "note": NOTE},
        {"operation": "drop"},
    ],
    ids=["add without a text", "revision without a text", "revision of nothing", "drop of nothing"],
)
def test_an_operation_that_says_too_little_is_refused(written: dict[str, object]) -> None:
    """A model will produce all four, and none of them can be acted on."""
    with pytest.raises(ValidationError):
        TypeAdapter(NotebookOperation).validate_python(written)


@pytest.mark.parametrize(
    "written",
    [
        {"operation": "add", "note": NOTE, "entry": 0},
        {"operation": "drop", "entry": 0, "note": NOTE},
    ],
    ids=["add aiming at a note", "drop carrying a text"],
)
def test_an_operation_that_says_too_much_is_refused(written: dict[str, object]) -> None:
    """An addition aims at nothing, and a deletion carries nothing.

    Refused rather than ignored, because the schema handed to the model says
    ``additionalProperties: false`` (D-035): a field quietly dropped here would
    be a promise the type does not keep.
    """
    with pytest.raises(ValidationError):
        TypeAdapter(NotebookOperation).validate_python(written)


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ({"operation": "add", "note": NOTE}, NotebookOperationName.ADD),
        ({"operation": "revise", "entry": 2, "note": NOTE}, NotebookOperationName.REVISE),
        ({"operation": "drop", "entry": 2}, NotebookOperationName.DROP),
    ],
    ids=["add", "revise", "drop"],
)
def test_the_three_well_formed_operations_are_accepted(
    written: dict[str, object], expected: NotebookOperationName
) -> None:
    """Guard the two tests above: they would pass on a model refusing everything."""
    parsed: AddNote | ReviseNote | DropNote = TypeAdapter(NotebookOperation).validate_python(
        written
    )

    assert parsed.operation is expected


# --- The notebook is rebuilt from the journal (D-088) ------------------------


class ScribblingAgent(Scripted):
    """Fills a notebook the way a model would: adds, then revises, then drops.

    Its moves are the silent agent's — what matters here is what it writes, and
    a table where somebody keeps naming people would end the game before the
    third turn ever happened.
    """

    def __init__(self) -> None:
        """Start with an empty notebook and nothing written yet."""
        self._turns = 0
        self._moves = SilentAgent()

    async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
        """Bid like the agent whose moves it plays."""
        return await self._moves.bid(view, journal)

    async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
        """Write one operation per turn, in the order add, revise, drop."""
        move = await self._moves.decide(view, journal)
        self._turns += 1
        return move.model_copy(update={"notebook": self._writes()})

    def _writes(self) -> tuple[NotebookOperation, ...]:
        match self._turns:
            case 1:
                return (AddNote(note=FIRST_NOTE), AddNote(note=SECOND_NOTE))
            case 2:
                return (ReviseNote(entry=0, note=REVISED_NOTE),)
            case 3:
                return (DropNote(entry=1),)
            case _:
                return ()


async def a_game_of_scribblers() -> tuple[GameResult, PlayerId]:
    """A game where every seat writes, and the seat whose notebook we read."""
    rng = create_rng(4)
    state = create_game(FORCED_DESIGNATION, rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: ScribblingAgent() for player in state.players}
    return await play_game(state, agents, max_rounds=10, rng=rng), state.players[0].id


async def test_a_notebook_is_rebuilt_from_the_journal() -> None:
    """What D-088 buys: a notebook survives a replay, and a reconnection (J8)."""
    result, writer = await a_game_of_scribblers()

    written = notebook_of(result.journal, writer)

    assert [note.note for note in written] == [REVISED_NOTE]


async def test_a_notebook_is_read_from_its_own_author_alone() -> None:
    """Rebuilt from the projected journal, so the filter of J3 is what protects it."""
    result, writer = await a_game_of_scribblers()
    someone_else = next(player for player in result.state.players if player.id != writer)

    theirs = notebook_of(
        project_journal(result.journal, Recipient.of(someone_else)),
        writer,
    )

    assert theirs == ()
