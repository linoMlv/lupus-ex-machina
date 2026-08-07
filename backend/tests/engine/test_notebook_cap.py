"""The notebook is capped, and the engine is what caps it (D-005)."""

from collections.abc import Sequence

import pytest

from lupus_ex_machina.agents.scripted import Scripted, SilentAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.events import (
    Event,
    IntentRejected,
)
from lupus_ex_machina.engine.notebook import notebook_of
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameRules
from lupus_ex_machina.engine.runner import GameResult, play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.turn import (
    AddNote,
    DropNote,
    NotebookOperation,
    ReviseNote,
    Turn,
)
from lupus_ex_machina.engine.views import PlayerView
from support.thinkers import (
    FORCED_DESIGNATION,
)

# --- The notebook is capped, and the engine is what caps it (D-005) ----------


class OverwritesEverything(Scripted):
    """Writes far more notes than the rules allow, and aims at notes that never existed.

    Exactly what a model does when the prompt slips: the cap has to be held by
    the engine, because a prompt asking nicely is not a cap.
    """

    def __init__(self, writes: tuple[NotebookOperation, ...]) -> None:
        """Take the operations this agent tries on its first turn."""
        self._writes = writes
        self._moves = SilentAgent()

    async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
        """Bid like the agent whose moves it plays."""
        return await self._moves.bid(view, journal)

    async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
        """Play a harmless move, and try every operation it was given."""
        move = await self._moves.decide(view, journal)
        written, self._writes = self._writes, ()
        return move.model_copy(update={"notebook": written})


async def a_game_where_one_seat_writes(
    writes: tuple[NotebookOperation, ...],
) -> tuple[GameResult, PlayerId]:
    """A game where a single seat tries those operations, and its identifier."""
    rng = create_rng(4)
    state = create_game(FORCED_DESIGNATION, rng=rng)
    writer = state.players[0].id
    agents: dict[PlayerId, Agent] = {
        player.id: OverwritesEverything(writes) if player.id == writer else SilentAgent()
        for player in state.players
    }
    return await play_game(state, agents, max_rounds=10, rng=rng), writer


async def test_a_notebook_never_grows_past_its_cap() -> None:
    """D-005 caps the notebook so its author has to choose what to keep."""
    cap = GameRules().debate.notebook_note_limit
    result, writer = await a_game_where_one_seat_writes(
        tuple(AddNote(note=f"Note numéro {rank}.") for rank in range(cap + 5))
    )

    assert len(notebook_of(result.journal, writer)) == cap


async def test_a_note_the_cap_refused_is_reported_rather_than_dropped() -> None:
    """Silence would leave an agent believing it wrote something it did not."""
    cap = GameRules().debate.notebook_note_limit
    result, writer = await a_game_where_one_seat_writes(
        tuple(AddNote(note=f"Note numéro {rank}.") for rank in range(cap + 5))
    )

    refusals = [
        event.payload
        for event in result.journal
        if isinstance(event.payload, IntentRejected) and event.payload.actor == writer
    ]

    assert len(refusals) == 5


@pytest.mark.parametrize(
    "written",
    [ReviseNote(entry=7, note="Une note qui n'existe pas."), DropNote(entry=7)],
    ids=["revising nothing", "dropping nothing"],
)
async def test_an_operation_aimed_at_a_note_that_does_not_exist_is_refused(
    written: NotebookOperation,
) -> None:
    """A model will refer to a note it never wrote, or one it already dropped."""
    result, writer = await a_game_where_one_seat_writes((written,))

    assert notebook_of(result.journal, writer) == ()
    assert [
        event
        for event in result.journal
        if isinstance(event.payload, IntentRejected) and event.payload.actor == writer
    ]
