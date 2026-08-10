"""Keeping a journal beyond the process that played the game.

JSON Lines, one fact per line. The format is chosen for what it makes cheap
rather than for elegance: a file readable by eye during debugging, a line that
can be appended without rewriting what precedes it, and a run cut short that
leaves a repairable file instead of an unparseable one.

Reading is strict on purpose. Blank lines are skipped, because a trailing
newline is not a fact, but anything else that is not a fact stops the read and
says which line it was. A journal is the source of truth of a game (D-040):
silently dropping the half line a crash left behind would hand back a game that
is subtly not the one that was played, and nothing downstream could tell.
"""

from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from lupus_ex_machina.engine.errors import EngineError
from lupus_ex_machina.engine.events import Event

ENCODING = "utf-8"

#: How the instant of a game is written into the name of its archive. Compact
#: and sortable, and without the colons a file name may not carry.
ARCHIVE_INSTANT = "%Y%m%dT%H%M%S"


class JournalFileError(EngineError):
    """A journal that cannot be read from where it was expected."""


def write_journal(path: Path, events: Iterable[Event]) -> None:
    """Write a whole journal, replacing whatever the file held before.

    One file holds one game. Appending a second game to an existing file would
    produce something that replays as neither.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = "".join(f"{event.model_dump_json()}\n" for event in events)
    path.write_text(lines, encoding=ENCODING)


def archive_journal(directory: Path, events: Iterable[Event], *, seed: int) -> Path:
    """File the journal of a finished game, beside the ones before it (D-104).

    A game is archived under a name of its own because :func:`write_journal`
    replaces what it is handed and one file holds one game: written to a fixed
    path, every game would erase the last.

    The name is the seed — which replays the game — and the instant it opened,
    read off the **first fact** rather than from a clock. The journal already
    carries the moment each of its facts happened, injected and replayable, so
    naming an archive needs no new dependency on the time of day.
    """
    recorded = tuple(events)
    if not recorded:
        raise JournalFileError("There is no game to archive: the journal holds no fact")

    opened = recorded[0].recorded_at.strftime(ARCHIVE_INSTANT)
    path = directory / f"game-{seed}-{opened}.jsonl"
    write_journal(path, recorded)
    return path


def read_journal(path: Path) -> tuple[Event, ...]:
    """Read back the journal a file holds."""
    try:
        raw = path.read_text(encoding=ENCODING)
    except OSError as unreadable:
        raise JournalFileError(f"There is no journal to read at {path}") from unreadable

    return tuple(
        _parse(line, number, path)
        for number, line in enumerate(raw.splitlines(), start=1)
        if line.strip()
    )


def _parse(line: str, number: int, path: Path) -> Event:
    try:
        return Event.model_validate_json(line)
    except ValidationError as malformed:
        raise JournalFileError(f"{path}, line {number} is not a recorded fact") from malformed
