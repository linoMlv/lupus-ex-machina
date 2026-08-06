"""A provider that answers without a network (GL-2, J7.1.6).

The whole of J7 and the whole of J8 lean on this: a game has to be playable in a
test, for free, instantly, and identically twice. It answers from a script when
it has one, and invents an answer when it does not.
"""

import pytest
from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.llm.errors import ModelAnswerError
from lupus_ex_machina.llm.fake import FakeCompletions, NothingToAnswerError
from lupus_ex_machina.llm.messages import Message, Role

QUESTION = (Message(role=Role.USER, content="Veux-tu parler ?"),)


class Answer(BaseModel):
    """The shape a model is asked to answer in."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    urgency: int = Field(ge=0, le=100)
    intention: str


async def test_it_answers_the_script_it_was_given_in_order() -> None:
    provider = FakeCompletions(
        script=[
            '{"urgency": 10, "intention": "D\'abord."}',
            '{"urgency": 90, "intention": "Puis."}',
        ]
    )

    first = await provider.complete(model="ministral-3b-latest", messages=QUESTION, schema=Answer)
    second = await provider.complete(model="ministral-3b-latest", messages=QUESTION, schema=Answer)

    assert (first.intention, second.intention) == ("D'abord.", "Puis.")


async def test_a_scripted_answer_of_the_wrong_shape_is_refused_like_a_real_one() -> None:
    """A fake that accepted what a provider would not would hide the bug it exists to catch."""
    provider = FakeCompletions(script=['{"urgency": 300, "intention": "Hors barème."}'])

    with pytest.raises(ModelAnswerError):
        await provider.complete(model="ministral-3b-latest", messages=QUESTION, schema=Answer)


async def test_it_invents_an_answer_once_the_script_runs_out() -> None:
    """A game asks far more than a script can hold; the rest has to be made up."""
    provider = FakeCompletions(
        invent=lambda schema, messages: '{"urgency": 50, "intention": "Improvisé."}'
    )

    answer = await provider.complete(model="ministral-3b-latest", messages=QUESTION, schema=Answer)

    assert answer.intention == "Improvisé."


async def test_it_says_so_rather_than_hanging_when_it_has_nothing_to_answer() -> None:
    """No script and no way to invent is a mistake in a test, and it should read as one."""
    provider = FakeCompletions()

    with pytest.raises(NothingToAnswerError):
        await provider.complete(model="ministral-3b-latest", messages=QUESTION, schema=Answer)


async def test_it_keeps_every_request_it_was_handed() -> None:
    """What makes a prompt testable: the fake is where a test reads what was sent (J7.2.6)."""
    provider = FakeCompletions(script=['{"urgency": 10, "intention": "Oui."}'])

    await provider.complete(
        model="mistral-small-latest", messages=QUESTION, schema=Answer, temperature=0.3
    )

    asked = provider.asked[0]
    assert asked.model == "mistral-small-latest"
    assert asked.messages == QUESTION
    assert asked.temperature == 0.3
