"""A seat played by a model (D-001, D-004).

What one seat *is*: two models, a temperament, and a context it is held to. The
asking happens here — the turning of an answer into a move that the engine will
be offered lives in :mod:`moves`, and the building of what is asked in
:mod:`prompting`.

Everything a seat is handed is measured before it is sent (D-063). A game of V1
never comes near its window, so nothing is ever cut; the mechanism is what keeps
that true if the word limits or the size of a table ever change.
"""

from collections.abc import Sequence

from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.events import Event
from lupus_ex_machina.engine.turn import (
    Reflection,
    Turn,
)
from lupus_ex_machina.engine.views import PlayerView
from lupus_ex_machina.llm.answers import BidAnswer, ReflectionAnswer, TurnAnswer
from lupus_ex_machina.llm.completions import Completions
from lupus_ex_machina.llm.context import ContextBudget, pruned
from lupus_ex_machina.llm.messages import Message, Role
from lupus_ex_machina.llm.moves import intent_of, notes_of
from lupus_ex_machina.llm.personalities import Temperament
from lupus_ex_machina.llm.prompting import Briefing, bid_prompt, system_prompt, turn_prompt
from lupus_ex_machina.llm.speech import truncated
from lupus_ex_machina.llm.tagging import spoken

#: The bounds an urgency stays within, whatever a temperament adds to it (D-002).
LOWEST_URGENCY, HIGHEST_URGENCY = 0, 100


class LlmAgent:
    """One seat, one temperament, two models (D-058, D-077)."""

    def __init__(
        self,
        *,
        completions: Completions,
        personality: Temperament,
        bidding_model: str,
        generation_model: str,
        temperature: float = 0.7,
        top_p: float = 1.0,
        budget: ContextBudget | None = None,
    ) -> None:
        """Take who answers for this seat, how it plays, and on which models.

        Two models rather than one: the auction is the call a game makes most
        often and runs on the cheap one, generation on the capable one. That is
        what makes a whole game affordable (D-077).

        A seat without a budget is one whose model declared no window (D-063):
        it is never pruned, which is also what every test that does not care
        about context gets.
        """
        self._completions = completions
        self._personality = personality
        self._bidding_model = bidding_model
        self._generation_model = generation_model
        self._temperature = temperature
        self._top_p = top_p
        self._budget = budget if budget is not None else ContextBudget()

    @property
    def personality(self) -> Temperament:
        """How this seat plays. Read by the spectator, when the option allows it (D-064)."""
        return self._personality

    @property
    def generation_model(self) -> str:
        """The model this seat thinks and speaks with (D-077)."""
        return self._generation_model

    @property
    def bidding_model(self) -> str:
        """The model this seat bids for the floor with (D-077)."""
        return self._bidding_model

    @property
    def budget(self) -> ContextBudget:
        """How much this seat may be handed at once, from its window (D-063)."""
        return self._budget

    async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
        """Say how badly this seat wants the floor (D-002).

        The temperament shifts the answer rather than merely colouring it
        (D-064): an introvert bids lower than it said it would, so it genuinely
        speaks less over a game.
        """
        answered = await self._completions.complete(
            model=self._bidding_model,
            messages=self._conversation(view, bid_prompt(view, journal=journal)),
            schema=BidAnswer,
            temperature=self._temperature,
            top_p=self._top_p,
        )
        return Bid(
            urgency=self._swayed(answered.urgency),
            intention=spoken(answered.intention) or answered.intention,
        )

    async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
        """Play a whole turn: think, write, and act (D-083)."""
        answered = await self._generate(view, journal, schema=TurnAnswer)
        return Turn(
            reasoning=truncated(answered.reasoning, view.limits.analysis_words),
            notebook=notes_of(answered.notebook, view),
            intent=intent_of(answered, view),
        )

    async def reflect(self, view: PlayerView, journal: Sequence[Event]) -> Reflection:
        """Take stock of the round that just closed, without acting (D-086)."""
        answered = await self._generate(view, journal, schema=ReflectionAnswer)
        return Reflection(
            reasoning=truncated(answered.reasoning, view.limits.analysis_words),
            notebook=notes_of(answered.notebook, view),
        )

    # --- Asking ---------------------------------------------------------------

    async def _generate[Answered: TurnAnswer | ReflectionAnswer](
        self, view: PlayerView, journal: Sequence[Event], *, schema: type[Answered]
    ) -> Answered:
        """Put the full prompt to the capable model and hand back its answer."""
        return await self._completions.complete(
            model=self._generation_model,
            messages=self._within_budget(view, journal),
            schema=schema,
            temperature=self._temperature,
            top_p=self._top_p,
        )

    def _within_budget(self, view: PlayerView, journal: Sequence[Event]) -> tuple[Message, ...]:
        """The conversation this turn is asked with, pruned only if it must be.

        Built whole first and measured, rather than pruned on a guess: D-063
        wants the elision to happen at the window and nowhere before it, so a
        game that fits — every game in V1 — is handed its full history.

        Only the turn is weighed. A bid carries the moment and one speech by
        construction (D-002, GL-7), so there is nothing in it for a budget to
        find, and measuring it would cost more than it saves.
        """
        whole = self._conversation(view, turn_prompt(view, journal=journal))
        if self._budget.holds(whole):
            return whole
        return self._conversation(view, turn_prompt(view, journal=pruned(journal, day=view.day)))

    def _conversation(self, view: PlayerView, asked: str) -> tuple[Message, ...]:
        """The standing instructions of this seat, then the question of the moment."""
        return (
            Message(
                role=Role.SYSTEM,
                content=system_prompt(
                    view, briefing=Briefing(personality=self._personality.description)
                ),
            ),
            Message(role=Role.USER, content=asked),
        )

    def _swayed(self, urgency: int) -> int:
        """An urgency, shifted by the temperament and kept on the scale (D-064)."""
        return max(LOWEST_URGENCY, min(HIGHEST_URGENCY, urgency + self._personality.urgency_bias))
