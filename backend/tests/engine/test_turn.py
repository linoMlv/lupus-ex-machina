"""What a player hands back when they are asked to play (D-083).

A turn is not an action alone: it is reading one's notebook, thinking the game
over, and only then deciding. The engine has to collect the whole of that,
because it is the only thing holding the journal — an agent recording its own
facts would be an agent writing into the source of truth (D-001).

Everything here is exercised by scripted agents, without a model (GL-2): what a
turn *contains* is J7.4's business, that it is collected at all is this one's.
"""

from collections.abc import Sequence

import pytest
from pydantic import TypeAdapter, ValidationError

from lupus_ex_machina.agents.scripted import AlwaysAccuseAgent, Scripted, SilentAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.events import (
    Event,
    IntentRejected,
    NotebookEntryRecorded,
    PrivateReasoningRecorded,
    SpeechDelivered,
    VoteResolved,
)
from lupus_ex_machina.engine.journal import project_journal
from lupus_ex_machina.engine.notebook import notebook_of
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameRules, NightOptions
from lupus_ex_machina.engine.runner import GameResult, play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.turn import (
    AddNote,
    DropNote,
    NotebookOperation,
    NotebookOperationName,
    Reflection,
    ReviseNote,
    Turn,
)
from lupus_ex_machina.engine.validation import BOOTSTRAP_DAY
from lupus_ex_machina.engine.views import PlayerView
from lupus_ex_machina.engine.visibility import Recipient

ANALYSIS = "Personne n'a rien dit d'utile pour l'instant."
NOTE = "Surveiller qui parle le moins."
FIRST_NOTE = "Adèle a parlé la première."
SECOND_NOTE = "Basile n'a rien dit."
REVISED_NOTE = "Adèle a parlé la première, et trop vite."

#: A pack made to leave every night with a victim, so a silent table still ends.
FORCED_DESIGNATION = GameRules(night=NightOptions(require_werewolf_target=True))


class ThinkingAgent(Scripted):
    """Plays like the accusing agent, but says what it was thinking first.

    The move itself is delegated rather than rewritten: what is under test is
    the thought travelling with it, and a second-hand copy of the accusing
    agent's rules would only be one more thing to keep in agreement.
    """

    def __init__(self) -> None:
        """Take the moves of a scripted agent, and think out loud on top."""
        self._moves = AlwaysAccuseAgent()

    async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
        """Bid like the agent whose moves it plays."""
        return await self._moves.bid(view, journal)

    async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
        """Hand back the same move, with an analysis and a note attached."""
        move = await self._moves.decide(view, journal)
        return move.model_copy(
            update={
                "reasoning": ANALYSIS,
                "notebook": (AddNote(note=NOTE),),
            }
        )


async def a_game_of_thinkers(seed: int = 3) -> GameResult:
    """One whole game where every seat thinks before it plays."""
    rng = create_rng(seed)
    state = create_game(GameRules(), rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: ThinkingAgent() for player in state.players}
    return await play_game(state, agents, rng=rng)


async def test_what_a_player_thought_before_acting_is_written_down() -> None:
    result = await a_game_of_thinkers()

    thoughts = [
        event.payload
        for event in result.journal
        if isinstance(event.payload, PrivateReasoningRecorded)
    ]

    assert thoughts, "a game where nobody thought would prove nothing"
    assert all(thought.reasoning == ANALYSIS for thought in thoughts)


async def test_what_a_player_wrote_in_their_notebook_is_written_down() -> None:
    result = await a_game_of_thinkers()

    notes = [
        event.payload
        for event in result.journal
        if isinstance(event.payload, NotebookEntryRecorded)
    ]

    assert notes, "a game where nobody wrote anything would prove nothing"
    assert all(note.note == NOTE for note in notes)


async def test_a_thought_never_reaches_the_shared_transcript() -> None:
    """The separation of D-004, held by the code rather than by a prompt (GL-3)."""
    result = await a_game_of_thinkers()

    spoken = [
        event.payload for event in result.journal if isinstance(event.payload, SpeechDelivered)
    ]

    assert all(ANALYSIS not in speech.speech for speech in spoken)
    assert all(NOTE not in speech.speech for speech in spoken)


async def test_a_player_who_thinks_nothing_leaves_nothing_behind() -> None:
    """A scripted agent has no thoughts, and the journal says so rather than inventing them."""
    rng = create_rng(3)
    state = create_game(GameRules(), rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: AlwaysAccuseAgent() for player in state.players}

    result = await play_game(state, agents, rng=rng)

    assert not [
        event
        for event in result.journal
        if isinstance(event.payload, PrivateReasoningRecorded | NotebookEntryRecorded)
    ]


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


# --- Thinking once more when the round closes (D-086) ------------------------

CLOSING_THOUGHT = "Le dépouillement change tout ce que je croyais."


class ThinksAgainAtTheClose(ThinkingAgent):
    """Thinks on its turn like any agent, and once more when the round closes."""

    async def reflect(self, view: PlayerView, journal: Sequence[Event]) -> Reflection:
        """Take stock of what the count and the resolution just taught."""
        return Reflection(reasoning=CLOSING_THOUGHT)


async def a_game_of_second_thoughts() -> GameResult:
    """A whole game where every seat thinks again at every close."""
    rng = create_rng(3)
    state = create_game(GameRules(), rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: ThinksAgainAtTheClose() for player in state.players}
    return await play_game(state, agents, rng=rng)


async def test_a_player_who_has_voted_thinks_again_when_the_round_closes() -> None:
    """D-086: voting ends the floor, not the thinking.

    The moment is chosen rather than incidental — the count and the resolution
    are what teaches a player the most in a whole round.
    """
    result = await a_game_of_second_thoughts()

    closing = [
        event
        for event in result.journal
        if isinstance(event.payload, PrivateReasoningRecorded)
        and event.payload.reasoning == CLOSING_THOUGHT
    ]

    assert closing, "nobody took stock at the close"


async def test_taking_stock_happens_after_the_count_rather_than_before() -> None:
    """Asked any earlier, it would be a second turn rather than a second thought."""
    result = await a_game_of_second_thoughts()
    counted = next(
        event.sequence for event in result.journal if isinstance(event.payload, VoteResolved)
    )
    took_stock = next(
        event.sequence
        for event in result.journal
        if isinstance(event.payload, PrivateReasoningRecorded)
        and event.payload.reasoning == CLOSING_THOUGHT
    )

    assert took_stock > counted


async def test_every_living_player_takes_stock_at_the_close() -> None:
    """Everyone at the table has voted by then, so everyone is asked (D-013).

    Day 1 is where the whole table is still there: its only legal vote is a
    blank one (D-032), so the round closes without eliminating anybody.
    """
    result = await a_game_of_second_thoughts()

    took_stock = {
        event.payload.player
        for event in result.journal
        if isinstance(event.payload, PrivateReasoningRecorded)
        and event.payload.reasoning == CLOSING_THOUGHT
        and event.day == BOOTSTRAP_DAY
    }

    assert len(took_stock) == len(result.state.players)
