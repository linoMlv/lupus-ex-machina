"""A hosted game whose models answer without a network (J8)."""

import asyncio

from lupus_ex_machina.configuration.schema import GameConfiguration
from lupus_ex_machina.configuration.system import SystemOptions
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.rules import GameRules, NightOptions, TableOptions
from lupus_ex_machina.engine.turn import Reflection
from lupus_ex_machina.hosting.broadcast import Heard
from lupus_ex_machina.hosting.game import HostedGame
from lupus_ex_machina.hosting.host import GameHost
from lupus_ex_machina.hosting.protocol import AskedFor, QuestionPut
from lupus_ex_machina.llm.completions import Completions
from lupus_ex_machina.llm.fake import FakeCompletions
from lupus_ex_machina.llm.throttling import Waiting
from support.seats import answering

#: Six players and a pack made to leave with a victim, so a table of models that
#: names nobody still reaches an end (D-078, D-081) — and quickly.
SHORT_GAME = GameConfiguration(
    rules=GameRules(
        table=TableOptions(player_count=6, seed=4),
        night=NightOptions(require_werewolf_target=True),
    )
)

#: Long enough that a game with anything to say has said it. Anything still
#: silent after this is waiting, not slow.
A_WHILE = 1.0


def a_completions() -> Completions:
    """A provider that invents plausible answers for any shape it is asked."""
    return FakeCompletions(invent=answering)


def a_provider(system: SystemOptions, waiting: Waiting) -> Completions:
    """The same, as the host asks for it: once the game and its audience exist.

    Two things arrive with the game rather than with the server: how the client
    waits (D-092), and who to tell that it is waiting (D-066).
    """
    return a_completions()


def a_host() -> GameHost:
    """A host whose games are played by models that reach nobody."""
    return GameHost(provider=a_provider)


async def a_question_put(heard: Heard) -> QuestionPut:
    """The first question a game puts to its person, off a listener's queue.

    Bounded in time on purpose: a game that never asks would otherwise hang the
    suite rather than fail it, and a hang says nothing about what went wrong.
    """
    async with asyncio.timeout(A_WHILE):
        while (told := await heard.get()) is not None:
            if isinstance(told, QuestionPut):
                return told
    raise AssertionError("the game ended without asking its person anything")


async def played_with_a_person(game: HostedGame, hand: Agent) -> None:
    """Play a whole game whose person answers everything with that hand.

    The hand is a scripted agent rather than a policy written here. What a
    person answers has to be a legal move like any other, and the agents of J2
    already know how to draw one from a view — so nothing on the path under test
    knows or cares who wrote the answer, which is the whole of D-096.

    **Bounded in time, and this is not a detail.** A game waits on its person for
    as long as it takes (D-097), so anything that breaks the way an answer gets
    back turns every test here into a hang instead of a failure — and a hang says
    nothing about what went wrong. Found by mutating the answer away and watching
    the suite stop rather than go red.
    """
    with game.listening() as heard:
        game.start()
        alongside = (
            asyncio.ensure_future(_keeping_up(game)),
            asyncio.ensure_future(_answering(game, heard, hand)),
        )
        try:
            async with asyncio.timeout(A_WHILE):
                await game.played()
        finally:
            for task in alongside:
                task.cancel()


async def _answering(game: HostedGame, heard: Heard, hand: Agent) -> None:
    """Answer every question the game puts to its person, until it has none left."""
    person = game.person
    assert person is not None, "a game with nobody at the table is never asked anything"

    while (told := await heard.get()) is not None:
        if isinstance(told, QuestionPut):
            person.answer(told.number, await _as_that_hand_would(hand, told))


async def _as_that_hand_would(hand: Agent, put: QuestionPut) -> Reflection:
    """What that hand answers the question with, whichever of the two it is."""
    if put.asked_for is AskedFor.TURN:
        return await hand.decide(put.view, ())
    return await hand.reflect(put.view, ())


async def played_out(game: HostedGame) -> None:
    """Play a whole game through, standing in for an audience that keeps up.

    A hosted game runs a few turns ahead of whoever is watching and waits once
    too many are in flight (J8.4). A test that wants a whole game therefore has
    to be an audience — which is the honest thing: without one, a game stopping
    early is the feature, not a hang.

    Bounded in time, like :func:`played_with_a_person` and for the same reason:
    a game may also wait on a person who will never answer (D-097), and a test
    that hangs on one says nothing about what went wrong.
    """
    game.start()
    watching = asyncio.ensure_future(_keeping_up(game))
    try:
        async with asyncio.timeout(A_WHILE):
            await game.played()
    finally:
        watching.cancel()


async def _keeping_up(game: HostedGame) -> None:
    """Confirm having shown everything, over and over, as fast as it is written."""
    while True:
        game.hands.shown(len(game.events))
        await asyncio.sleep(0)
