"""A client that waits says so, rather than seeming to hang (J8.4.4, D-066).

A provider refusing for rate reasons is survived by waiting (J7.1), and until
now nobody was told. On a screen that is a scene which stops with nothing to
explain it — precisely what D-066 refuses: the wait is a first-class event, not
an absence.

The waits are collected rather than slept through, like everywhere else: what
matters is what the client *would* have announced.
"""

import httpx2
from pydantic import BaseModel, ConfigDict

from lupus_ex_machina.llm.backoff import RetryPolicy
from lupus_ex_machina.llm.client import ChatClient
from lupus_ex_machina.llm.messages import Message, Role

BASE_URL = "https://api.example.test/v1"


class Answer(BaseModel):
    """The shape a model is asked to answer in."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    urgency: int


def refusing(times: int) -> httpx2.MockTransport:
    """A transport that answers "too many requests" that many times, then relents."""
    refusals = 0

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal refusals
        if refusals < times:
            refusals += 1
            return httpx2.Response(429)
        return httpx2.Response(200, json={"choices": [{"message": {"content": '{"urgency": 10}'}}]})

    return httpx2.MockTransport(respond)


async def asking(client: ChatClient) -> None:
    await client.complete(
        model="ministral-3b-latest",
        messages=(Message(role=Role.USER, content="Veux-tu parler ?"),),
        schema=Answer,
    )


async def test_a_client_announces_every_wait_it_takes() -> None:
    announced: list[float] = []
    client = ChatClient(
        base_url=BASE_URL,
        api_key="clef",
        transport=refusing(3),
        sleep=lambda seconds: _nothing(),
        retries=RetryPolicy(),
        waiting=announced.append,
    )

    await asking(client)

    assert announced == [1.0, 2.0, 4.0], "each wait, as long as it is about to be"


async def test_a_client_nobody_listens_to_waits_just_the_same() -> None:
    """Announcing is something a caller adds, never something the client needs."""
    client = ChatClient(
        base_url=BASE_URL,
        api_key="clef",
        transport=refusing(1),
        sleep=lambda seconds: _nothing(),
        retries=RetryPolicy(),
    )

    await asking(client)


async def test_a_client_that_never_waits_announces_nothing() -> None:
    announced: list[float] = []
    client = ChatClient(
        base_url=BASE_URL,
        api_key="clef",
        transport=refusing(0),
        sleep=lambda seconds: _nothing(),
        retries=RetryPolicy(),
        waiting=announced.append,
    )

    await asking(client)

    assert announced == []


async def _nothing() -> None:
    """Stand in for sleeping, without taking any of it."""
