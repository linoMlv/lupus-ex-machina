"""Keeping the journal of a finished game beside the ones before it (J8.0.3).

An archive, not a resume: the journal is written once the game is over, and a
server that restarts mid-game loses it (D-093). What matters here is that a
second game does not overwrite the first — `write_journal` replaces the file it
is handed, and one file holds one game, so a fixed path would keep exactly one
archive no matter how many games were played (D-104).
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lupus_ex_machina.engine.events import PhaseEntered, SpeechDelivered
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.persistence import (
    JournalFileError,
    archive_journal,
    read_journal,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.state import GameState

SPEAKER = PlayerId("p0")


def ticking(*instants: datetime) -> Iterator[datetime]:
    """A clock that reads those instants in turn, then holds the last one."""
    yield from instants
    while True:
        yield instants[-1]


def a_journal(*, at: datetime) -> Journal:
    """A journal of one short day, opened at that instant."""
    clock = ticking(at)
    journal = Journal(clock=lambda: next(clock))
    state = GameState.initial(()).entering(Phase.DAY, day=1)
    journal.record(PhaseEntered(phase=Phase.DAY, day=1), at=state)
    journal.record(SpeechDelivered(speaker=SPEAKER, speech="Bonsoir."), at=state)
    return journal


def test_two_games_archived_in_the_same_place_leave_two_files(tmp_path: Path) -> None:
    """The whole point: a fixed path would keep only the last game ever played."""
    morning = a_journal(at=datetime(2026, 8, 10, 9, 30, tzinfo=UTC))
    evening = a_journal(at=datetime(2026, 8, 10, 21, 15, tzinfo=UTC))

    archive_journal(tmp_path, morning.events, seed=1)
    archive_journal(tmp_path, evening.events, seed=1)

    assert len(list(tmp_path.glob("*.jsonl"))) == 2


def test_an_archive_reads_back_as_the_game_that_was_played(tmp_path: Path) -> None:
    journal = a_journal(at=datetime(2026, 8, 10, 9, 30, tzinfo=UTC))

    written = archive_journal(tmp_path, journal.events, seed=7)

    assert read_journal(written) == journal.events


def test_an_archive_is_named_for_the_game_it_holds(tmp_path: Path) -> None:
    """Findable by eye: the seed replays it, the instant tells which run it was."""
    journal = a_journal(at=datetime(2026, 8, 10, 21, 15, tzinfo=UTC))

    written = archive_journal(tmp_path, journal.events, seed=7)

    assert "7" in written.stem, "the seed, which replays it"
    assert "20260810" in written.stem, "and the day it was played"


def test_the_directory_is_made_when_it_is_not_there_yet(tmp_path: Path) -> None:
    journal = a_journal(at=datetime(2026, 8, 10, 9, 30, tzinfo=UTC))

    written = archive_journal(tmp_path / "archives" / "2026", journal.events, seed=1)

    assert written.exists()


def test_a_game_that_recorded_nothing_is_refused_rather_than_filed(tmp_path: Path) -> None:
    """A journal with no facts is not a game, and it has no instant to be named for.

    Loud rather than silent: an empty archive on disk would look like a game
    that was played and lost, which is worse than one that was never written.
    """
    with pytest.raises(JournalFileError, match="no game"):
        archive_journal(tmp_path, (), seed=1)
