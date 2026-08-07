"""Seats played by a fake provider: what they answer, and what they are made of."""

from lupus_ex_machina.configuration.agents import Personality
from lupus_ex_machina.engine.rules import GameRules, NightOptions
from lupus_ex_machina.llm.agent import LlmAgent
from lupus_ex_machina.llm.answers import (
    BidAnswer,
    ReflectionAnswer,
    TurnAnswer,
)
from lupus_ex_machina.llm.fake import FakeCompletions
from lupus_ex_machina.llm.personalities import personalities

#: A pack made to leave every night with a victim, so a table of models that
#: never names anybody still reaches an end (D-078, D-081).
FORCED = GameRules(night=NightOptions(require_werewolf_target=True))


def answering(schema: type, messages: object) -> str:
    """A plausible answer for each shape, with nothing but a thought in it.

    Enough to play a whole game: nobody names anybody, so the day is closed by
    the forced vote and the night by the lot (D-060, D-081).
    """
    if schema is BidAnswer:
        return BidAnswer(urgency=50, intention="Peut-être parler.").model_dump_json()
    if schema is ReflectionAnswer:
        return ReflectionAnswer(reasoning="Ce tour m'a appris peu de choses.").model_dump_json()
    return TurnAnswer(reasoning="Je regarde qui parle le plus.").model_dump_json()


def seated(provider: FakeCompletions, personality: Personality = Personality.INTJ) -> LlmAgent:
    return LlmAgent(
        completions=provider,
        personality=personalities()[personality],
        bidding_model="ministral-3b-latest",
        generation_model="mistral-small-latest",
    )
