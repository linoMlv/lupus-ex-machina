"""A seat played by a model (D-001, D-004).

Two translations, and nothing else: a projected view becomes a prompt, and an
answer becomes an intent. Neither direction is allowed to be clever. What the
model asks for is put to the engine as it stands, and the validator decides —
an agent that quietly corrected an illegal move would be an agent making rules
(D-001).

Names in, names out. A model only ever sees what is spoken at the table, so it
answers with names; a name nobody bears is dropped rather than guessed at, and
the rest of the turn is kept. Models invent players, and losing a whole turn
over one invented name would cost far more than the field is worth.
"""

from collections.abc import Sequence
from typing import assert_never

from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.events import Event
from lupus_ex_machina.engine.intents import (
    Intent,
    PriorityPoint,
    RoleAction,
    SharePriority,
    TakeTurn,
    Vote,
    Wait,
)
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.turn import (
    AddNote,
    DropNote,
    NotebookOperation,
    Reflection,
    ReviseNote,
    Turn,
)
from lupus_ex_machina.engine.views import PlayerView
from lupus_ex_machina.llm.answers import BidAnswer, ReflectionAnswer, TurnAnswer
from lupus_ex_machina.llm.completions import Completions
from lupus_ex_machina.llm.messages import Message, Role
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
    ) -> None:
        """Take who answers for this seat, how it plays, and on which models.

        Two models rather than one: the auction is the call a game makes most
        often and runs on the cheap one, generation on the capable one. That is
        what makes a whole game affordable (D-077).
        """
        self._completions = completions
        self._personality = personality
        self._bidding_model = bidding_model
        self._generation_model = generation_model
        self._temperature = temperature
        self._top_p = top_p

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
            notebook=self._notes(answered.notebook, view),
            intent=self._intent(answered, view),
        )

    async def reflect(self, view: PlayerView, journal: Sequence[Event]) -> Reflection:
        """Take stock of the round that just closed, without acting (D-086)."""
        answered = await self._generate(view, journal, schema=ReflectionAnswer)
        return Reflection(
            reasoning=truncated(answered.reasoning, view.limits.analysis_words),
            notebook=self._notes(answered.notebook, view),
        )

    # --- Asking ---------------------------------------------------------------

    async def _generate[Answered: TurnAnswer | ReflectionAnswer](
        self, view: PlayerView, journal: Sequence[Event], *, schema: type[Answered]
    ) -> Answered:
        """Put the full prompt to the capable model and hand back its answer."""
        return await self._completions.complete(
            model=self._generation_model,
            messages=self._conversation(view, turn_prompt(view, journal=journal)),
            schema=schema,
            temperature=self._temperature,
            top_p=self._top_p,
        )

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

    # --- Making an answer into a move -----------------------------------------

    @staticmethod
    def _notes(
        written: tuple[NotebookOperation, ...], view: PlayerView
    ) -> tuple[NotebookOperation, ...]:
        """The notebook operations, each cut to the words a note may hold (D-021)."""
        return tuple(_trimmed(operation, view.limits.notebook_words) for operation in written)

    def _intent(self, answered: TurnAnswer, view: PlayerView) -> Intent:
        """The move a turn amounts to, in the order the night and the day expect.

        A spread first, then a power, then a turn at the floor: they are the
        three shapes the phases offer, and a model that filled in two of them
        gets the one its phase can take. Whether it *may* is the validator's
        answer, not this one's (D-001).
        """
        if spread := self._spread(answered, view):
            return spread
        if power := self._power(answered, view):
            return power
        return self._floor(answered, view) or Wait()

    def _spread(self, answered: TurnAnswer, view: PlayerView) -> Intent | None:
        """The pack's allocation, dropping the prey nobody at the table is (D-008)."""
        allocations = tuple(
            PriorityPoint(target=found, points=share.points)
            for share in answered.priorities
            if (found := _named(view, share.target)) is not None
        )
        return SharePriority(allocations=allocations) if allocations else None

    @staticmethod
    def _power(answered: TurnAnswer, view: PlayerView) -> Intent | None:
        """The power a turn uses, when it names one and aims it at somebody real."""
        if answered.action is None or answered.target is None:
            return None
        target = _named(view, answered.target)
        return RoleAction(action=answered.action, target=target) if target is not None else None

    @staticmethod
    def _floor(answered: TurnAnswer, view: PlayerView) -> Intent | None:
        """Speaking, voting, or both — the three ways a turn at the floor goes (D-028)."""
        said = truncated(spoken(answered.speech or ""), view.limits.speech_words) or None
        named = _named(view, answered.vote) if answered.vote else None
        vote = Vote(target=named) if named is not None or answered.votes_blank else None

        if said is None and vote is None:
            return None
        return TakeTurn(
            speech=said,
            addressed=_named(view, answered.addressed),
            accused=_named(view, answered.accused),
            vote=vote,
        )


def _named(view: PlayerView, name: str | None) -> PlayerId | None:
    """The player who goes by that name at this table, or nobody.

    Case and surrounding spaces are forgiven — a model writes "camille " often
    enough — but nothing else is guessed at: a name close to two players would
    make the engine pick for them.
    """
    if name is None:
        return None
    wanted = name.strip().casefold()
    return next(
        (player.id for player in view.players if player.name.casefold() == wanted),
        None,
    )


def _trimmed(operation: NotebookOperation, words: int) -> NotebookOperation:
    """The same operation, with its text cut to the words a note may hold.

    A deletion carries no text, which is exactly why it is its own type: there
    is nothing here to cut, and nothing to check for.
    """
    match operation:
        case AddNote() | ReviseNote():
            return operation.model_copy(update={"note": truncated(operation.note, words)})
        case DropNote():
            return operation
        case _:  # pragma: no cover - the union is closed, mypy proves this is dead
            assert_never(operation)
