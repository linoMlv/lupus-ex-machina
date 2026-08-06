"""Waiting out a provider that says no, without freezing a game (D-047, D-066).

The waits are collected rather than slept through: what matters is how long the
client *would* have waited, and a suite that actually waited a minute for one
test would never be run.
"""

import json

import httpx2
import pytest
from pydantic import BaseModel, ConfigDict

from lupus_ex_machina.llm.backoff import RetryPolicy
from lupus_ex_machina.llm.client import ChatClient, Message, Role, ThrottledError

BASE_URL = "https://api.example.test/v1"


class Answer(BaseModel):
    """The shape a model is asked to answer in."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    urgency: int


class Waits:
    """A stand-in for sleeping, keeping what it was asked to wait."""

    def __init__(self) -> None:
        """Start with nothing waited for."""
        self.seconds: list[float] = []

    async def __call__(self, seconds: float) -> None:
        """Record the wait instead of taking it."""
        self.seconds.append(seconds)


def refusing(times: int, *, headers: dict[str, str] | None = None) -> httpx2.MockTransport:
    """A transport that answers "too many requests" that many times, then relents."""
    refusals = 0

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal refusals
        if refusals < times:
            refusals += 1
            return httpx2.Response(429, headers=headers or {})
        return httpx2.Response(200, json={"choices": [{"message": {"content": '{"urgency": 10}'}}]})

    return httpx2.MockTransport(respond)


async def asking(client: ChatClient) -> Answer:
    return await client.complete(
        model="ministral-3b-latest",
        messages=(Message(role=Role.USER, content="Veux-tu parler ?"),),
        schema=Answer,
    )


async def test_a_refused_request_is_waited_out_and_tried_again() -> None:
    waits = Waits()
    client = ChatClient(
        base_url=BASE_URL, api_key="clef", transport=refusing(1), sleep=waits, retries=RetryPolicy()
    )

    answer = await asking(client)

    assert answer.urgency == 10
    assert waits.seconds == [RetryPolicy().first_delay_seconds]


async def test_the_first_wait_is_short_and_the_next_ones_double() -> None:
    """D-066: a long first step empties the display buffer and the scene freezes."""
    waits = Waits()
    client = ChatClient(
        base_url=BASE_URL, api_key="clef", transport=refusing(4), sleep=waits, retries=RetryPolicy()
    )

    await asking(client)

    assert waits.seconds == [1.0, 2.0, 4.0, 8.0]


async def test_the_wait_stops_doubling_at_its_ceiling() -> None:
    """Beyond the ceiling it stays there: D-047 caps at a minute, then holds."""
    waits = Waits()
    policy = RetryPolicy(first_delay_seconds=30.0, maximum_delay_seconds=60.0)
    client = ChatClient(
        base_url=BASE_URL, api_key="clef", transport=refusing(3), sleep=waits, retries=policy
    )

    await asking(client)

    assert waits.seconds == [30.0, 60.0, 60.0]


async def test_the_delay_the_provider_asks_for_wins() -> None:
    """`Retry-After` is what the provider knows and the policy is only guessing."""
    waits = Waits()
    client = ChatClient(
        base_url=BASE_URL,
        api_key="clef",
        transport=refusing(1, headers={"Retry-After": "7"}),
        sleep=waits,
        retries=RetryPolicy(),
    )

    await asking(client)

    assert waits.seconds == [7.0]


async def test_a_provider_that_never_relents_gives_up_rather_than_waiting_forever() -> None:
    """A game has to fail loudly rather than hang: J8 shows the wait, not a freeze."""
    waits = Waits()
    policy = RetryPolicy(attempts=3)
    client = ChatClient(
        base_url=BASE_URL, api_key="clef", transport=refusing(99), sleep=waits, retries=policy
    )

    with pytest.raises(ThrottledError):
        await asking(client)

    assert len(waits.seconds) == policy.attempts - 1, "waited between attempts, not after the last"


async def test_an_error_that_is_not_a_rate_limit_is_not_waited_out() -> None:
    """Retrying a refused key would only spend a minute discovering it again."""
    waits = Waits()
    client = ChatClient(
        base_url=BASE_URL,
        api_key="mauvaise-clef",
        transport=httpx2.MockTransport(lambda request: httpx2.Response(401, json={})),
        sleep=waits,
        retries=RetryPolicy(),
    )

    with pytest.raises(httpx2.HTTPStatusError):
        await asking(client)

    assert waits.seconds == []


def test_the_policy_of_the_project_is_the_one_the_decisions_describe() -> None:
    """D-066 for the short first step, D-047 for the ceiling."""
    policy = RetryPolicy()

    assert policy.first_delay_seconds == 1.0
    assert policy.maximum_delay_seconds == 60.0
    assert json.dumps(policy.model_dump()), "a policy is configuration, so it serialises"


async def test_a_delay_the_provider_words_rather_than_counts_falls_back_to_the_policy() -> None:
    """`Retry-After` may be an HTTP date, and a game must not stop over a header."""
    waits = Waits()
    client = ChatClient(
        base_url=BASE_URL,
        api_key="clef",
        transport=refusing(1, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}),
        sleep=waits,
        retries=RetryPolicy(),
    )

    await asking(client)

    assert waits.seconds == [RetryPolicy().first_delay_seconds]
