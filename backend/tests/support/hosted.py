"""A hosted game whose models answer without a network (J8)."""

import asyncio

from lupus_ex_machina.configuration.schema import GameConfiguration
from lupus_ex_machina.configuration.system import SystemOptions
from lupus_ex_machina.engine.rules import GameRules, NightOptions, TableOptions
from lupus_ex_machina.hosting.game import HostedGame
from lupus_ex_machina.hosting.host import GameHost
from lupus_ex_machina.llm.completions import Completions
from lupus_ex_machina.llm.fake import FakeCompletions
from support.seats import answering

#: Six players and a pack made to leave with a victim, so a table of models that
#: names nobody still reaches an end (D-078, D-081) — and quickly.
SHORT_GAME = GameConfiguration(
    rules=GameRules(
        table=TableOptions(player_count=6, seed=4),
        night=NightOptions(require_werewolf_target=True),
    )
)


def a_completions() -> Completions:
    """A provider that invents plausible answers for any shape it is asked."""
    return FakeCompletions(invent=answering)


def a_provider(system: SystemOptions) -> Completions:
    """The same, as the host asks for it: built once the game is known (D-092)."""
    return a_completions()


def a_host() -> GameHost:
    """A host whose games are played by models that reach nobody."""
    return GameHost(provider=a_provider)


async def played_out(game: HostedGame) -> None:
    """Play a whole game through, standing in for an audience that keeps up.

    A hosted game runs a few turns ahead of whoever is watching and waits once
    too many are in flight (J8.4). A test that wants a whole game therefore has
    to be an audience — which is the honest thing: without one, a game stopping
    early is the feature, not a hang.
    """
    game.start()
    watching = asyncio.ensure_future(_keeping_up(game))
    try:
        await game.played()
    finally:
        watching.cancel()


async def _keeping_up(game: HostedGame) -> None:
    """Confirm having shown everything, over and over, as fast as it is written."""
    while True:
        game.shown(len(game.events))
        await asyncio.sleep(0)
