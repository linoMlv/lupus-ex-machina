"""What a person's answer has to be to be taken (J8.5.2, D-096).

Three refusals, and each one guards against a way the game and the person could
end up talking about two different moments.

**One answer per question.** Several connections share the one identity of a
played game, so two tabs would otherwise play two moves for the same turn.

**An answer names the question it answers.** A slow tab, or one that came back,
answers the question it last saw — which may no longer be the one standing.

**An answer has the shape that was asked for.** A turn *is* a stock-taking with
a move on it, so a turn offered where a stock-taking was wanted would be taken
with its move quietly dropped.
"""

import asyncio

from lupus_ex_machina.engine.intents import Wait
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.turn import Reflection, Turn
from lupus_ex_machina.engine.views import PlayerView, project
from lupus_ex_machina.hosting.human import HumanAgent
from lupus_ex_machina.hosting.protocol import AskedFor, Question, QuestionPut

A_MOMENT = 1.0


def a_view() -> PlayerView:
    """The view of one seat of a game just dealt. Any of them will do here."""
    state = create_game(rng=create_rng(4))
    return project(state, state.players[0].id)


def a_person(said: list[Question] | None = None) -> HumanAgent:
    """A person at some seat, announcing to a list when one is given."""
    heard = said if said is not None else []
    return HumanAgent(PlayerId("p0"), announce=heard.append)


async def a_question_standing(person: HumanAgent) -> QuestionPut:
    """Let the game get as far as putting its question, and hand it back."""
    async with asyncio.timeout(A_MOMENT):
        while (standing := person.question) is None:
            await asyncio.sleep(0)
    return standing


async def test_the_first_answer_to_a_question_wins_and_the_next_is_refused() -> None:
    person = a_person()
    playing = asyncio.ensure_future(person.decide(a_view(), ()))
    standing = await a_question_standing(person)

    taken = person.answer(standing.number, Turn(reasoning="Le premier.", intent=Wait()))
    second = person.answer(standing.number, Turn(reasoning="Le second.", intent=Wait()))

    assert taken, "the first answer is the one that plays"
    assert not second, "and a second tab does not play a second move for the same turn"
    assert (await playing).reasoning == "Le premier."


async def test_an_answer_naming_another_question_is_refused() -> None:
    person = a_person()
    playing = asyncio.ensure_future(person.decide(a_view(), ()))
    standing = await a_question_standing(person)

    stale = person.answer(standing.number - 1, Turn(intent=Wait()))

    assert not stale, "an answer to the question before is not an answer to this one"
    assert person.question is not None, "and the question is still standing"

    playing.cancel()


async def test_an_answer_of_the_wrong_shape_is_refused() -> None:
    """A stock-taking where a turn was asked for carries no move at all."""
    person = a_person()
    playing = asyncio.ensure_future(person.decide(a_view(), ()))
    standing = await a_question_standing(person)

    assert standing.asked_for is AskedFor.TURN
    assert not person.answer(standing.number, Reflection(reasoning="Je réfléchis."))

    playing.cancel()


async def test_a_turn_where_a_stock_taking_was_asked_for_is_refused_too() -> None:
    """The other way round, which is the one that would pass unnoticed.

    A turn satisfies the type a stock-taking is declared with, so without this
    it would be taken and its move dropped without a word.
    """
    person = a_person()
    taking_stock = asyncio.ensure_future(person.reflect(a_view(), ()))
    standing = await a_question_standing(person)

    assert standing.asked_for is AskedFor.REFLECTION
    assert not person.answer(standing.number, Turn(intent=Wait()))

    taking_stock.cancel()


async def test_answering_when_nothing_was_asked_is_refused() -> None:
    assert not a_person().answer(1, Turn(intent=Wait()))
