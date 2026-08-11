"""Everything that asks an agent for something and writes down what came back.

One object holds what a running game accumulates — the agents, the journal, the
count of refused intents — so that the phases themselves stay functions of a
state. It is also the single door to the journal: the engine holds the record,
and an agent writing its own facts would be writing into the source of truth
(D-001).
"""

import asyncio
from collections.abc import Mapping

from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.events import (
    Event,
    EventPayload,
    IntentRejected,
    PhaseEntered,
    PrivateReasoningRecorded,
)
from lupus_ex_machina.engine.intents import Intent
from lupus_ex_machina.engine.journal import Journal, project_journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.recollection import recollected
from lupus_ex_machina.engine.rng import Rng
from lupus_ex_machina.engine.runner import notes
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.turn import NotebookOperation, Reflection
from lupus_ex_machina.engine.validation import validate_intent
from lupus_ex_machina.engine.views import PlayerView, project
from lupus_ex_machina.engine.visibility import Recipient

Agents = Mapping[PlayerId, Agent]

# What an agent is handed of the record: its own facts, already filtered.
Events = tuple[Event, ...]


class Scribe:
    """The agents, the journal, and the tally of what the rules would not take."""

    def __init__(self, agents: Agents, journal: Journal, rng: Rng) -> None:
        """Take the table's agents, the journal to write to, and the game's generator."""
        self._agents = agents
        self._journal = journal
        self._rng = rng
        self._rejected = 0

    @property
    def rng(self) -> Rng:
        """The generator the game was dealt from — the only source of chance (D-081)."""
        return self._rng

    @property
    def events(self) -> Events:
        """Everything recorded so far, unfiltered. For the engine only."""
        return self._journal.events

    @property
    def rejected(self) -> int:
        """How many intents the rules have refused since the game opened."""
        return self._rejected

    # --- Writing ---------------------------------------------------------

    def record(self, payload: EventPayload, at: GameState) -> None:
        """Write one fact down. Its audience is carried by the fact itself (D-009)."""
        self._journal.record(payload, at=at)

    def enter(self, state: GameState, phase: Phase, *, day: int | None = None) -> GameState:
        """Move to another phase and record it. The only way a phase is entered."""
        state = state.entering(phase, day=day)
        self.record(PhaseEntered(phase=state.phase, day=state.day), at=state)
        return state

    def refuse(self, state: GameState, actor: PlayerId, reason: str) -> None:
        """Count and record something the rules would not take."""
        self._rejected += 1
        self.record(IntentRejected(actor=actor, reason=reason), at=state)

    # --- Asking ----------------------------------------------------------

    def what_they_see(self, state: GameState, player: PlayerId) -> tuple[PlayerView, Events]:
        """The two things an agent is ever handed: its view, and its own journal.

        Both filtered here, at the source: an agent able to read the whole
        journal would be one line away from every secret in the game (D-046).

        Two filters rather than one, and they answer different questions. The
        projection says **who may know** (D-009); the recollection says what may
        still be **looked up** of rounds that are over (D-111). Everyone was
        entitled to a count when it was read out — what the second one takes away
        is the re-reading, which is why it cannot live inside the first.
        """
        return (
            project(state, player),
            recollected(
                project_journal(self._journal.events, Recipient.of(state.player(player))),
                day=state.day,
                information=state.rules.information,
            ),
        )

    async def ask(self, state: GameState, player: PlayerId) -> Intent:
        """Ask a player for their turn, and write down what they made of it.

        Recorded in the order a turn happens (D-083): the thought first, then
        the note it led to, then the move. Recorded *here*, so that every way of
        asking a player anything goes through the same place.
        """
        turn = await self._agents[player].decide(*self.what_they_see(state, player))
        self.write_down_what_was_thought(state, player, turn)
        return turn.intent

    async def bid_of(self, state: GameState, player: PlayerId) -> Bid:
        """Ask one player how badly they want the floor (D-002).

        The small call of the game, and by far the most frequent one — the whole
        reason a seat declares a second, faster model (D-077, GL-7).
        """
        return await self._agents[player].bid(*self.what_they_see(state, player))

    async def let_them_take_stock(self, state: GameState, players: tuple[PlayerId, ...]) -> None:
        """Ask those players what they make of things, with nothing to play (D-086).

        All at once, like an auction, and for the same reason: this is one large
        model call per player, and they do not depend on one another (GL-7).
        """
        thoughts = await asyncio.gather(
            *(
                self._agents[player].reflect(*self.what_they_see(state, player))
                for player in players
            )
        )
        for player, thought in zip(players, thoughts, strict=True):
            self.write_down_what_was_thought(state, player, thought)

    def accepts(self, state: GameState, actor: PlayerId, intent: Intent) -> bool:
        """Whether the rules would take that intent, without applying anything."""
        try:
            validate_intent(state, actor, intent)
        except IllegalIntentError:
            return False
        return True

    # --- Private thought -------------------------------------------------

    def write_down_what_was_thought(
        self, state: GameState, player: PlayerId, reflection: Reflection
    ) -> None:
        """Record a player's private reasoning and notebook, if they had any.

        Both are their author's own (D-004): the audience is carried by the
        facts themselves, so nothing here can widen it.
        """
        if reflection.reasoning is not None:
            self.record(
                PrivateReasoningRecorded(player=player, reasoning=reflection.reasoning), at=state
            )
        for operation in reflection.notebook:
            self._write(state, player, operation)

    def _write(self, state: GameState, player: PlayerId, operation: NotebookOperation) -> None:
        """Apply one operation on a notebook, or refuse it out loud (D-005).

        A refusal is recorded rather than passed over: an operation that vanished
        silently would leave its author believing they wrote something.
        """
        refusal = notes.refusal_of(
            operation,
            self._journal.events,
            player,
            cap=state.rules.debate.notebook_note_limit,
        )
        if refusal is not None:
            self.refuse(state, player, refusal)
            return

        self.record(notes.fact_of(operation, self._journal.events, player), at=state)
