"""Handing the facts of a running game to whoever is listening (J8.3, D-094).

The observer of the journal notes; this is what it notes into. One queue per
listener, because two clients read at their own pace and a single queue would
have the slower one stealing facts from the faster.

Nothing here filters: a broadcaster carries what was recorded, and projection
happens at the edge, once per recipient (D-046).
"""

import asyncio
from datetime import UTC, datetime

from lupus_ex_machina.engine.events import Event, PhaseEntered
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.hosting.broadcast import Broadcaster, Told
from lupus_ex_machina.hosting.protocol import RateLimited
from support.hosted import SHORT_GAME, a_host, played_out


def a_day() -> GameState:
    return GameState.initial(()).entering(Phase.DAY, day=2)


def a_fact(day: int = 2) -> PhaseEntered:
    return PhaseEntered(phase=Phase.DAY, day=day)


def spoken(told: Told | None) -> Event:
    """The fact a listener was handed, refusing anything that is not one."""
    assert isinstance(told, Event), "a fact was expected, and something else came"
    return told


def an_event(sequence: int = 0) -> Event:
    return Event(
        sequence=sequence,
        recorded_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
        phase=Phase.DAY,
        day=2,
        payload=a_fact(),
    )


async def test_a_listener_is_handed_the_facts_that_follow_it() -> None:
    broadcaster = Broadcaster()

    with broadcaster.listening() as heard:
        broadcaster.note(an_event())

        assert spoken(await heard.get()).sequence == 0


async def test_every_listener_is_handed_the_same_fact() -> None:
    """One queue each: a shared one would have the first reader eat the fact."""
    broadcaster = Broadcaster()

    with broadcaster.listening() as first, broadcaster.listening() as second:
        broadcaster.note(an_event(7))

        for listener in (first, second):
            assert spoken(await listener.get()).sequence == 7


async def test_a_listener_that_has_gone_is_no_longer_written_to() -> None:
    """A queue nobody reads would grow for as long as the game lasts."""
    broadcaster = Broadcaster()
    with broadcaster.listening() as heard:
        pass

    broadcaster.note(an_event())

    assert heard.empty()


async def test_a_game_writing_its_journal_feeds_the_listeners() -> None:
    """The whole point: what a journal records is what a client is told."""
    broadcaster = Broadcaster()
    journal = Journal(observer=broadcaster.note)

    with broadcaster.listening() as heard:
        journal.record(a_fact(), at=a_day())

        told = await asyncio.wait_for(heard.get(), timeout=1)
        assert spoken(told).payload == a_fact()


async def test_noting_a_fact_nobody_listens_to_is_not_an_error() -> None:
    """A game plays whether or not anybody has come to watch it."""
    Broadcaster().note(an_event())


async def test_a_closed_broadcast_tells_every_listener_it_is_over() -> None:
    """Without an end, a listener waits on a game that will never speak again."""
    broadcaster = Broadcaster()

    with broadcaster.listening() as heard:
        broadcaster.close()

        assert await heard.get() is None


async def test_a_game_that_reaches_its_end_closes_its_broadcast() -> None:
    """So a client is told the game is over rather than left holding the line."""
    game = a_host().create(SHORT_GAME)

    with game.listening() as heard:
        await played_out(game)
        heard_after = [heard.get_nowait() for _ in range(heard.qsize())]

    assert heard_after[-1] is None


async def test_a_game_that_is_given_up_closes_its_broadcast_too() -> None:
    """An abandoned game is just as over, from a listener's point of view."""
    game = a_host().create(SHORT_GAME)

    with game.listening() as heard:
        game.start()
        await game.abandon()
        heard_after = [heard.get_nowait() for _ in range(heard.qsize())]

    assert heard_after[-1] is None


async def test_somebody_arriving_after_the_end_is_told_at_once() -> None:
    """Otherwise a client connecting to a finished game holds the line for ever.

    The end was said before they were listening, so it has to be said again —
    a closed broadcast is closed for whoever comes next, not only for those who
    were there.
    """
    broadcaster = Broadcaster()
    broadcaster.close()

    with broadcaster.listening() as heard:
        assert await asyncio.wait_for(heard.get(), timeout=1) is None


async def test_a_hosted_game_hands_every_fact_it_records_to_a_listener() -> None:
    """End to end: a game playing itself is a stream, without knowing it is one."""
    game = a_host().create(SHORT_GAME)

    with game.listening() as heard:
        await played_out(game)

    assert heard.qsize() == len(game.events) + 1, "every fact, no fact twice, and the end"


async def test_a_wait_reaches_the_listeners_like_a_fact_does() -> None:
    """D-066: the wait is an event of its own, never an absence of events.

    It is not a fact of the journal — it says nothing about the game, only about
    the provider — so it travels beside them rather than among them.
    """
    broadcaster = Broadcaster()

    with broadcaster.listening() as heard:
        broadcaster.note_a_wait(12.0)

        told = await asyncio.wait_for(heard.get(), timeout=1)
        assert told == RateLimited(seconds=12.0)


async def test_a_wait_nobody_listens_to_is_not_an_error() -> None:
    """A game waits on its provider whether or not anybody has come to watch."""
    Broadcaster().note_a_wait(3.0)
