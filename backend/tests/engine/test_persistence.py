"""Writing a journal to disk and reading it back.

JSON Lines, one fact per line: readable by eye, appendable without rewriting,
and repairable when a run is cut short — none of which a single big JSON array
gives. A journal that survives the round trip is what makes a game replayable
after the process that played it is gone (D-040).
"""

from pathlib import Path

import pytest

from lupus_ex_machina.agents.scripted import RandomAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.events import Event, PhaseEntered, SpeechDelivered
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.persistence import (
    JournalFileError,
    read_journal,
    write_journal,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.replay import replay
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.runner import play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState

SPEAKER = PlayerId("p0")

# Everything that has ever broken a naive line-based format: accents, ligatures,
# quotation marks, and a line break inside the text itself.
AWKWARD_SPEECH = "Adèle a dit : « c'est lui ! »\nMoi, j'en suis sûr — cœur \"net\"."


def a_journal(*speeches: str) -> Journal:
    journal = Journal()
    state = GameState.initial(()).entering(Phase.DAY, day=2)
    journal.record(PhaseEntered(phase=Phase.DAY, day=2), at=state)
    for speech in speeches:
        journal.record(SpeechDelivered(speaker=SPEAKER, speech=speech), at=state)
    return journal


def test_a_journal_read_back_is_the_journal_that_was_written(tmp_path: Path) -> None:
    journal = a_journal("Bonsoir.", "Je me méfie de Camille.")
    path = tmp_path / "game.jsonl"

    write_journal(path, journal.events)

    assert read_journal(path) == journal.events


def test_accents_and_line_breaks_survive_the_round_trip(tmp_path: Path) -> None:
    """Speech is free text, and it will be read back into prompts in J7."""
    path = tmp_path / "game.jsonl"
    write_journal(path, a_journal(AWKWARD_SPEECH).events)

    spoken = read_journal(path)[-1].payload

    assert isinstance(spoken, SpeechDelivered)
    assert spoken.speech == AWKWARD_SPEECH


def test_a_journal_file_holds_one_fact_per_line(tmp_path: Path) -> None:
    """The line break inside the speech above must not become a second fact."""
    journal = a_journal(AWKWARD_SPEECH, "Bonsoir.")
    path = tmp_path / "game.jsonl"

    write_journal(path, journal.events)

    assert len(path.read_text(encoding="utf-8").splitlines()) == len(journal)


def test_a_journal_file_is_readable_by_eye(tmp_path: Path) -> None:
    """Accents stay accents rather than escape sequences: this gets read by humans."""
    path = tmp_path / "game.jsonl"
    write_journal(path, a_journal("Je me méfie de Adèle.").events)

    assert "Je me méfie de Adèle." in path.read_text(encoding="utf-8")


def test_writing_a_journal_creates_the_directory_it_belongs_in(tmp_path: Path) -> None:
    path = tmp_path / "games" / "2026" / "game.jsonl"

    write_journal(path, a_journal("Bonsoir.").events)

    assert read_journal(path)


def test_a_whole_game_survives_a_trip_through_a_file(tmp_path: Path) -> None:
    """The point of the exercise: a game replayed from disk is the same game."""
    rng = create_rng(3)
    state = create_game(8, rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: RandomAgent(rng=rng) for player in state.players}
    result = play_game(state, agents, journal=Journal())

    path = tmp_path / "game.jsonl"
    write_journal(path, result.journal)

    assert replay(read_journal(path)) == result.state


# --- A file that is not a journal --------------------------------------------


def test_blank_lines_are_ignored(tmp_path: Path) -> None:
    """A trailing newline is not a fact, and neither is an empty line."""
    path = tmp_path / "game.jsonl"
    write_journal(path, a_journal("Bonsoir.").events)
    path.write_text(path.read_text(encoding="utf-8") + "\n\n", encoding="utf-8")

    assert len(read_journal(path)) == 2


def test_a_line_that_is_not_a_fact_is_refused_by_its_number(tmp_path: Path) -> None:
    """Half a line is what a run cut short leaves behind; it must be loud."""
    path = tmp_path / "game.jsonl"
    write_journal(path, a_journal("Bonsoir.").events)
    path.write_text(path.read_text(encoding="utf-8") + '{"sequence": 2, "phase"', encoding="utf-8")

    with pytest.raises(JournalFileError, match="line 3"):
        read_journal(path)


def test_a_journal_that_is_not_there_is_refused(tmp_path: Path) -> None:
    with pytest.raises(JournalFileError, match="no journal"):
        read_journal(tmp_path / "never-played.jsonl")


def test_an_empty_journal_writes_an_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "game.jsonl"

    write_journal(path, ())

    assert read_journal(path) == ()


def test_writing_a_journal_replaces_whatever_was_there(tmp_path: Path) -> None:
    """A journal file holds one game, whole — never two half games."""
    path = tmp_path / "game.jsonl"
    write_journal(path, a_journal("Un.", "Deux.", "Trois.").events)

    write_journal(path, a_journal("Bonsoir.").events)

    assert len(read_journal(path)) == 2


def test_a_journal_read_back_holds_real_events(tmp_path: Path) -> None:
    """Guard against a reader that returns dictionaries and looks convincing."""
    path = tmp_path / "game.jsonl"
    write_journal(path, a_journal("Bonsoir.").events)

    assert all(isinstance(event, Event) for event in read_journal(path))
