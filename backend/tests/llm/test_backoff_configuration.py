"""Where the waits of the client come from (J8.0, D-092).

The settings existed, were validated, were documented — and nothing read them.
A policy nobody derives from the configuration is a form control that changes
nothing, which J6 forbids. These tests watch the derivation *and* what it
changes, because the defect was never in the values: it was in the wiring.
"""

import httpx2
from pydantic import BaseModel, ConfigDict

from lupus_ex_machina.configuration.system import SystemOptions
from lupus_ex_machina.llm.backoff import retries_for
from lupus_ex_machina.llm.client import ChatClient
from lupus_ex_machina.llm.messages import Message, Role

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


async def waits_of(options: SystemOptions, *, refused: int) -> list[float]:
    """What a client built from those options waits through that many refusals."""
    waits = Waits()
    client = ChatClient(
        base_url=BASE_URL,
        api_key="clef",
        transport=refusing(refused),
        sleep=waits,
        retries=retries_for(options),
    )

    await client.complete(
        model="ministral-3b-latest",
        messages=(Message(role=Role.USER, content="Veux-tu parler ?"),),
        schema=Answer,
    )
    return waits.seconds


async def test_a_client_waits_what_its_configuration_says_rather_than_the_default() -> None:
    """The defect of J7, in one assertion: these values had no effect at all."""
    unusual = SystemOptions(
        backoff_first_delay_seconds=5.0,
        backoff_maximum_delay_seconds=20.0,
    )

    assert await waits_of(unusual, refused=3) == [5.0, 10.0, 20.0]


async def test_the_defaults_of_the_configuration_are_the_policy_of_the_decisions() -> None:
    """D-066 for the short first step, D-047 for the ceiling — unchanged."""
    assert await waits_of(SystemOptions(), refused=3) == [1.0, 2.0, 4.0]


async def test_how_many_attempts_are_made_is_configured_like_the_delays() -> None:
    """A policy whose delays are settings and whose patience is not is half a setting.

    J8.0.2: `attempts` lived in the code with no way to reach it, which is the
    same defect as the delays in a smaller size.
    """
    stubborn = SystemOptions(backoff_attempts=3)

    assert retries_for(stubborn).attempts == 3
    assert len(await waits_of(stubborn, refused=2)) == 2, "waits between attempts, not after"
