"""How a person asks for the floor, and what asking is worth (J8.5.1, D-107).

A bid is **read off the button, never waited for**. The floor is auctioned after
every turn, some twenty-five times a day of play: waiting on a person each time
would have them answer twenty-five times over just to say they have nothing to
add, and would stop the game between every turn.

Asking is not taking. A request goes into the auction and is weighed there like
anybody else's — recency, quota and all (D-002). Taking the floor outright is
the other button, and it does not bid at all (D-014).
"""

import asyncio

from lupus_ex_machina.engine.intents import TakeTurn, Wait
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.turn import Turn
from lupus_ex_machina.hosting.human import WANTS_NOTHING, WANTS_THE_FLOOR, HumanAgent
from lupus_ex_machina.hosting.protocol import Question
from support.persons import a_view_at_the_floor, a_view_of_the_opening_night

A_MOMENT = 1.0


def a_person(said: list[Question] | None = None) -> HumanAgent:
    heard = said if said is not None else []
    return HumanAgent(PlayerId("p0"), announce=heard.append)


async def a_question_standing(person: HumanAgent) -> int:
    """Let the game get as far as putting its question, and hand back its number."""
    async with asyncio.timeout(A_MOMENT):
        while (standing := person.question) is None:
            await asyncio.sleep(0)
    return standing.number


async def test_a_person_who_has_not_asked_for_the_floor_is_not_in_the_auction() -> None:
    """And answering costs nothing: a bid is read, never waited for (D-107)."""
    bid = await a_person().bid(a_view_at_the_floor(), ())

    assert bid.urgency == WANTS_NOTHING


async def test_asking_for_the_floor_bids_for_it_at_once() -> None:
    person = a_person()

    person.request_the_floor()

    assert (await person.bid(a_view_at_the_floor(), ())).urgency == WANTS_THE_FLOOR


async def test_a_request_stands_until_the_floor_is_actually_won() -> None:
    """Spent on the auction instead, a request lost to a better bid would vanish.

    The person would then have to press the button again after every single
    turn, which is not what asking for the floor means.
    """
    person = a_person()
    person.request_the_floor()

    await person.bid(a_view_at_the_floor(), ())

    assert (await person.bid(a_view_at_the_floor(), ())).urgency == WANTS_THE_FLOOR


async def test_winning_the_floor_spends_the_request() -> None:
    """Otherwise one press would hand its owner the floor for the rest of the day."""
    person = a_person()
    person.request_the_floor()
    speaking = asyncio.ensure_future(person.decide(a_view_at_the_floor(), ()))
    person.answer(await a_question_standing(person), Turn(intent=TakeTurn(speech="Me voilà.")))
    await speaking

    assert (await person.bid(a_view_at_the_floor(), ())).urgency == WANTS_NOTHING


async def test_a_turn_they_could_not_speak_in_leaves_the_request_alone() -> None:
    """A night wakes a role, it does not hand out the floor (D-083).

    Spending the request there would quietly swallow a person's wish to speak in
    the day that follows, in the one moment they cannot see it happen.
    """
    person = a_person()
    person.request_the_floor()
    waking = asyncio.ensure_future(person.decide(a_view_of_the_opening_night(), ()))
    person.answer(await a_question_standing(person), Turn(intent=Wait()))
    await waking

    assert (await person.bid(a_view_at_the_floor(), ())).urgency == WANTS_THE_FLOOR
