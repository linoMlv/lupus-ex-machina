"""A turn carries what was thought, and only speech is shared (D-004)."""

from lupus_ex_machina.agents.scripted import AlwaysAccuseAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.events import (
    NotebookEntryRecorded,
    PrivateReasoningRecorded,
    SpeechDelivered,
)
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameRules
from lupus_ex_machina.engine.runner import play_game
from lupus_ex_machina.engine.setup import create_game
from support.thinkers import ANALYSIS, NOTE, a_game_of_thinkers

# --- A turn carries what was thought, and only speech is shared (D-004) -----


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
