"""The one place a game is hosted (D-045, D-101).

V1 hosts a single game at a time, so this holds one and refuses a second while
it stands. Refusing rather than replacing is the point: the game already there
is somebody's evening, and a creation that silently swept it away would be the
one gesture nobody can undo.

A game that has ended, or been given up, no longer holds the place — it stays
readable, it simply stops being in the way.
"""

from collections.abc import Callable

from lupus_ex_machina.configuration.schema import GameConfiguration
from lupus_ex_machina.configuration.system import SystemOptions
from lupus_ex_machina.hosting.errors import NoGameError, OneGameAtATimeError
from lupus_ex_machina.hosting.game import HostedGame
from lupus_ex_machina.hosting.stage import Stage
from lupus_ex_machina.llm.completions import Completions
from lupus_ex_machina.llm.throttling import Waiting

#: The stages in which a game still holds the place.
UNDERWAY = (Stage.CREATED, Stage.PLAYING)

#: How a provider is obtained for a game about to be dealt. It takes the system
#: settings of *that* game because the retry policy is one of them (D-092): a
#: client built once at start-up would have no game to read a policy from, and
#: would quietly fall back on its own defaults.
Provider = Callable[[SystemOptions, Waiting], Completions]


class GameHost:
    """Whatever game is being hosted right now, if any."""

    def __init__(self, *, provider: Provider) -> None:
        """Take how to obtain the provider each game will be played by."""
        self._provider = provider
        self._current: HostedGame | None = None

    @property
    def current(self) -> HostedGame | None:
        """The game being hosted, or nothing."""
        return self._current

    def create(self, configuration: GameConfiguration) -> HostedGame:
        """Deal a new game, unless one is still underway."""
        if self._current is not None and self._current.stage in UNDERWAY:
            raise OneGameAtATimeError("Une partie est déjà en cours. Terminez-la ou abandonnez-la.")
        self._current = HostedGame(configuration, provider=self._provider)
        return self._current

    async def abandon(self) -> None:
        """Give up the game being hosted, and free the place at once."""
        if self._current is None:
            raise NoGameError("Il n'y a aucune partie à abandonner.")
        await self._current.abandon()
        self._current = None
