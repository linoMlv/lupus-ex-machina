"""J8.5.0 — the seat a person plays is never played without them (D-096).

The engine holds no notion of a human: an agent answers when asked, and that is
the whole of the contract (D-001). What changes when a game is dealt in player
mode is *who* answers for one seat — and the observable consequence, the one
asserted here, is that such a game no longer reaches its end on its own.

Left to a model, the seat would be played and the game would run to a winner
without the person ever being asked anything. That is the failure this file
exists to make loud.
"""

import asyncio

import pytest

from lupus_ex_machina.agents.scripted import RandomAgent, RogueAgent
from lupus_ex_machina.engine.events import IntentRejected
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.victory import Outcome
from lupus_ex_machina.hosting.game import HostedGame
from lupus_ex_machina.hosting.protocol import AskedFor
from lupus_ex_machina.hosting.stage import Stage
from support.hosted import a_provider, a_question_put, played_out, played_with_a_person
from support.persons import PLAYED_FROM_SEAT_ZERO

#: Long enough for the same game, watched, to be played out several times over.
#: A game still at its opening night after this is one that is waiting, not one
#: that is merely slow.
LONG_ENOUGH_TO_HAVE_FINISHED = 1.0


async def test_a_game_played_from_a_seat_waits_at_the_first_thing_it_asks_its_person() -> None:
    """It stops where the person is asked, and stays there (D-096, D-097).

    Asserting the phase as well as the wait is what keeps this from passing on
    any hang at all: the game has to have gone as far as its opening night and
    no further, which is exactly where seat zero is first asked to play.
    """
    game = HostedGame(PLAYED_FROM_SEAT_ZERO, provider=a_provider)

    with pytest.raises(TimeoutError):
        async with asyncio.timeout(LONG_ENOUGH_TO_HAVE_FINISHED):
            await played_out(game)

    assert game.state.phase is Phase.NIGHT_ZERO, "the game went on without its person"
    assert game.stage is Stage.PLAYING, "and it is waiting rather than finished"

    await game.abandon()


async def test_the_question_a_game_puts_to_its_person_reaches_whoever_listens() -> None:
    """A wait nobody is told about is a game that looks broken (J8.5.0b).

    The question carries the view, because the view is what says what may be
    done — and it is the person's own, the same one an agent is handed (GL-3).
    """
    game = HostedGame(PLAYED_FROM_SEAT_ZERO, provider=a_provider)
    person = game.person
    assert person is not None, "a game dealt in player mode has somebody at the table"

    with game.listening() as heard:
        game.start()
        put = await a_question_put(heard)

    await game.abandon()

    assert put.asked_for is AskedFor.TURN, "the opening night asks for a turn"
    assert put.view.self_id == person.player, "and it is that person's own view"


async def test_a_client_arriving_late_is_told_what_the_game_is_waiting_on() -> None:
    """Announced only, a question put before somebody connected would be lost.

    The game would then wait on an answer nobody knew was owed — the same gap
    between a history and a subscription that D-102 closes for the facts.
    """
    game = HostedGame(PLAYED_FROM_SEAT_ZERO, provider=a_provider)
    person = game.person
    assert person is not None

    with game.listening() as heard:
        game.start()
        await a_question_put(heard)

    standing = person.question
    await game.abandon()

    assert standing is not None, "the question is readable, not merely announced"
    assert standing.asked_for is AskedFor.TURN


async def test_a_game_whose_person_answers_is_played_to_its_end() -> None:
    """What the person answers is what the engine plays (J8.5.2).

    Reaching an end *is* the assertion, given the test above: a game whose
    person answers nothing never leaves its opening night. Every turn of this
    one — a word, a ballot, a power used at night — therefore went through the
    answer, and there is no second path it could have taken.
    """
    game = HostedGame(PLAYED_FROM_SEAT_ZERO, provider=a_provider)

    await played_with_a_person(game, RandomAgent(rng=create_rng(4)))

    assert game.stage is Stage.OVER
    assert game.outcome in tuple(Outcome)


async def test_what_a_person_answers_is_judged_by_the_rules_like_anybody_elses() -> None:
    """An illegal move costs the person their turn, and is written down (D-110).

    No special case, and none available either: an agent holds a view and never
    the state (D-001, GL-3), so nothing at the edge could judge a move without
    keeping a second copy of the rules. What the person is given instead is the
    refusal itself, in the journal they read.
    """
    game = HostedGame(PLAYED_FROM_SEAT_ZERO, provider=a_provider)
    person = game.person
    assert person is not None

    await played_with_a_person(game, RogueAgent())

    refused = [
        event
        for event in game.events
        if isinstance(event.payload, IntentRejected) and event.payload.actor == person.player
    ]
    assert refused, "the rules refused what the person tried, and said so out loud"
    assert game.stage is Stage.OVER, "and the game carried on without them"
