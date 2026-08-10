"""Watching a journal as it is written (J8.3, D-094).

How a game in progress becomes a stream. The journal is already the one place a
fact is written down, so an observer here catches every fact by construction —
there is no second door to remember.

**It is handed the fact, and it notes it.** Nothing here emits: the observer runs
inside the engine's own task, so anything it did over a network would make the
game wait on a client. Projecting and sending happen elsewhere, on the events it
put aside.
"""

from lupus_ex_machina.engine.events import Event, PhaseEntered, SpeechDelivered
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.state import GameState

SPEAKER = PlayerId("p0")


def a_day() -> GameState:
    return GameState.initial(()).entering(Phase.DAY, day=2)


def test_every_fact_reaches_the_observer_as_it_is_written() -> None:
    seen: list[Event] = []
    journal = Journal(observer=seen.append)
    state = a_day()

    journal.record(PhaseEntered(phase=Phase.DAY, day=2), at=state)
    journal.record(SpeechDelivered(speaker=SPEAKER, speech="Bonsoir."), at=state)

    assert [event.payload for event in seen] == [
        PhaseEntered(phase=Phase.DAY, day=2),
        SpeechDelivered(speaker=SPEAKER, speech="Bonsoir."),
    ]


def test_the_observer_is_handed_the_whole_fact_ready_to_be_sent() -> None:
    """Sequence, instant and phase included: it is what a client is sent (D-099).

    Rebuilding any of that outside the journal would be a second description of
    when a fact happened, and the first one is right here.
    """
    seen: list[Event] = []
    journal = Journal(observer=seen.append)

    journal.record(PhaseEntered(phase=Phase.DAY, day=2), at=a_day())

    assert seen == list(journal.events)


def test_a_journal_nobody_watches_records_just_the_same() -> None:
    """Watching is something a caller adds, never something the engine needs."""
    journal = Journal()

    journal.record(PhaseEntered(phase=Phase.DAY, day=2), at=a_day())

    assert len(journal) == 1
