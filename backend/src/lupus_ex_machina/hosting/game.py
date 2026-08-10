"""One game, hosted: dealt on creation, played once somebody starts it (D-103).

Creating and starting are two gestures. Creating deals the table and fixes the
seed; nothing is played and no model is asked anything until it is started,
which is what keeps a game nobody is watching yet from spending the call budget.

The game runs as a task rather than inside a request: a request that played a
game would take an hour to answer. What it leaves behind is the journal, and the
journal is where everything else reads from — the state is *derived* from it
(D-040) rather than kept alongside, so there is no second copy to fall out of
step with the game that was played.
"""

import asyncio
from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager, suppress
from typing import TYPE_CHECKING

from lupus_ex_machina.configuration.schema import GameConfiguration
from lupus_ex_machina.engine.events import Event
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.replay import replay
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.runner import play_game
from lupus_ex_machina.engine.runner.controls import Pacing
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.victory import Outcome
from lupus_ex_machina.hosting.broadcast import Broadcaster, Heard
from lupus_ex_machina.hosting.errors import AlreadyStartedError
from lupus_ex_machina.hosting.lead import turns_of_lead
from lupus_ex_machina.hosting.stage import Stage
from lupus_ex_machina.llm.agent import LlmAgent
from lupus_ex_machina.llm.table import seat_agents

if TYPE_CHECKING:
    from lupus_ex_machina.hosting.host import Provider


class HostedGame:
    """A game that has been dealt, and may be played."""

    def __init__(self, configuration: GameConfiguration, *, provider: "Provider") -> None:
        """Deal the table this configuration describes. Nothing is played yet.

        The audience is built before the client on purpose: a client is asked
        for once there is somebody to tell that it is waiting (D-066), and the
        other order makes that impossible.
        """
        seed = configuration.rules.table.seed
        self._configuration = configuration
        self._rng = create_rng(seed)
        self._opening = create_game(configuration.rules, rng=self._rng)
        self._broadcaster = Broadcaster()
        self._journal = Journal(observer=self._broadcaster.note)
        completions = provider(configuration.system, self._broadcaster.note_a_wait)
        self._agents: Mapping[PlayerId, LlmAgent] = seat_agents(
            self._opening,
            configuration.agents,
            completions=completions,
            seed=seed,
            system=configuration.system,
        )
        self._pacing = Pacing(turns_in_flight=turns_of_lead(configuration))
        self._stage = Stage.CREATED
        self._task: asyncio.Task[None] | None = None
        self._outcome: Outcome | None = None

    @property
    def configuration(self) -> GameConfiguration:
        """What this game was dealt from."""
        return self._configuration

    @property
    def stage(self) -> Stage:
        """Where the game is in its life."""
        return self._stage

    @property
    def outcome(self) -> Outcome | None:
        """Who won, once there is a winner."""
        return self._outcome

    @property
    def players(self) -> tuple[Player, ...]:
        """The table as it was dealt. Who is *alive* is read off the state."""
        return self._opening.players

    @property
    def events(self) -> Sequence[Event]:
        """Everything recorded so far, unfiltered. Projected before it is sent."""
        return self._journal.events

    @property
    def state(self) -> GameState:
        """The game as it stands, rebuilt from its journal (D-040).

        Derived rather than kept: a state held alongside the journal would be a
        second description of the same game, and this project has learned what
        happens when two of those drift apart.

        Replayed **under the rules this game was dealt with**. Rules are not
        facts and so are not in the journal: a replay told nothing rebuilds a
        game under the defaults, which would answer "spectator" about a game
        somebody is playing — and that answer decides who is sent what (D-100).
        """
        recorded = self._journal.events
        if not recorded:
            return self._opening
        return replay(recorded, rules=self._configuration.rules)

    def shown(self, sequence: int) -> None:
        """Take note that a client has displayed everything up to that fact.

        This is what lets the game go on: it runs a few turns ahead of whoever
        is watching (D-023) and waits once too many are in flight — one single
        turn when somebody is *playing*, so an absolute priority is always read
        before the next turn (D-014).
        """
        self._pacing.shown(sequence)

    def listening(self) -> AbstractContextManager[Heard]:
        """Listen to the facts this game records, for as long as the block lasts.

        What comes out is **unfiltered**: it is projected once per recipient, at
        the edge, because that is where the recipient is known (D-046).
        """
        return self._broadcaster.listening()

    def start(self) -> None:
        """Set the game playing. It runs on its own from here."""
        if self._stage is not Stage.CREATED:
            raise AlreadyStartedError(f"This game is already {self._stage}")
        self._stage = Stage.PLAYING
        self._task = asyncio.create_task(self._play())

    async def played(self) -> None:
        """Wait for the game to reach its end. Returns at once if it never started."""
        if self._task is not None:
            await self._task

    async def abandon(self) -> None:
        """Give the game up, stopping it if it is running.

        Awaited to its end rather than merely cancelled: a task still unwinding
        would go on writing to the journal of a game the user has left.
        """
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        self._broadcaster.close()
        self._stage = Stage.ABANDONED

    async def _play(self) -> None:
        """Play the game to its end, and remember who won.

        The broadcast is closed whatever happens, a game given up included: a
        listener told nothing would hold the line on a game nobody is playing.
        """
        try:
            result = await play_game(
                self._opening,
                dict(self._agents),
                journal=self._journal,
                pacing=self._pacing,
                rng=self._rng,
            )
            self._outcome = result.outcome
            self._stage = Stage.OVER
        finally:
            self._broadcaster.close()
