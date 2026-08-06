"""Talking to a model over the OpenAI protocol (D-043, D-035).

Never over the network: every test here answers through a mock transport, which
is what keeps the suite free, fast and offline (GL-2). What is under test is the
request the client builds and what it makes of the answer — not the provider.
"""

import json
from typing import Any

import httpx2
import pytest
from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.llm.client import ChatClient
from lupus_ex_machina.llm.errors import ModelAnswerError
from lupus_ex_machina.llm.messages import Message, Role

BASE_URL = "https://api.example.test/v1"
API_KEY = "clef-de-test"


class Answer(BaseModel):
    """The shape a model is asked to answer in."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    urgency: int = Field(ge=0, le=100)
    intention: str


def answering(payload: object, *, seen: list[httpx2.Request] | None = None) -> httpx2.MockTransport:
    """A transport that always answers with that payload, keeping the requests."""

    def respond(request: httpx2.Request) -> httpx2.Response:
        if seen is not None:
            seen.append(request)
        return httpx2.Response(
            200, json={"choices": [{"message": {"content": json.dumps(payload)}}]}
        )

    return httpx2.MockTransport(respond)


def client_of(transport: httpx2.MockTransport) -> ChatClient:
    return ChatClient(base_url=BASE_URL, api_key=API_KEY, transport=transport)


def body_of(request: httpx2.Request) -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads(request.content)
    return parsed


async def test_an_answer_comes_back_as_the_model_it_was_asked_for() -> None:
    client = client_of(answering({"urgency": 42, "intention": "Répondre à Camille."}))

    answer = await client.complete(
        model="ministral-3b-latest",
        messages=(Message(role=Role.USER, content="Veux-tu parler ?"),),
        schema=Answer,
    )

    assert answer == Answer(urgency=42, intention="Répondre à Camille.")


async def test_the_request_carries_the_key_and_goes_to_the_completions_endpoint() -> None:
    seen: list[httpx2.Request] = []
    client = client_of(answering({"urgency": 0, "intention": "Rien."}, seen=seen))

    await client.complete(
        model="ministral-3b-latest",
        messages=(Message(role=Role.USER, content="Veux-tu parler ?"),),
        schema=Answer,
    )

    assert str(seen[0].url) == f"{BASE_URL}/chat/completions"
    assert seen[0].headers["authorization"] == f"Bearer {API_KEY}"


async def test_the_request_asks_for_the_strict_schema_of_the_answer() -> None:
    """D-035: the shape is imposed rather than hoped for."""
    seen: list[httpx2.Request] = []
    client = client_of(answering({"urgency": 0, "intention": "Rien."}, seen=seen))

    await client.complete(
        model="ministral-3b-latest",
        messages=(Message(role=Role.USER, content="Veux-tu parler ?"),),
        schema=Answer,
    )

    response_format = body_of(seen[0])["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"] == Answer.model_json_schema()


async def test_the_request_carries_the_model_and_its_parameters() -> None:
    """Two models per seat and their settings are what D-077 and D-058 configure."""
    seen: list[httpx2.Request] = []
    client = client_of(answering({"urgency": 0, "intention": "Rien."}, seen=seen))

    await client.complete(
        model="mistral-small-latest",
        messages=(Message(role=Role.SYSTEM, content="Tu joues au Loup-Garou."),),
        schema=Answer,
        temperature=0.3,
        top_p=0.9,
    )

    body = body_of(seen[0])
    assert body["model"] == "mistral-small-latest"
    assert body["temperature"] == 0.3
    assert body["top_p"] == 0.9
    assert body["messages"] == [{"role": "system", "content": "Tu joues au Loup-Garou."}]


async def test_an_answer_that_does_not_fit_the_schema_is_asked_again() -> None:
    """A valid JSON can still be a wrong one, so the client says what was wrong."""
    answers = [
        {"urgency": 300, "intention": "Hors barème."},
        {"urgency": 30, "intention": "Correct cette fois."},
    ]
    seen: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(
            200, json={"choices": [{"message": {"content": json.dumps(answers[len(seen) - 1])}}]}
        )

    client = client_of(httpx2.MockTransport(respond))

    answer = await client.complete(
        model="ministral-3b-latest",
        messages=(Message(role=Role.USER, content="Veux-tu parler ?"),),
        schema=Answer,
    )

    assert answer.urgency == 30
    assert len(seen) == 2, "asked exactly once more"
    assert "urgency" in body_of(seen[1])["messages"][-1]["content"], "told what was wrong"


async def test_an_answer_that_never_fits_the_schema_gives_up_cleanly() -> None:
    """Two tries and no more: a model that will not comply costs a turn, not a game."""
    client = client_of(answering({"urgency": 300, "intention": "Toujours hors barème."}))

    with pytest.raises(ModelAnswerError):
        await client.complete(
            model="ministral-3b-latest",
            messages=(Message(role=Role.USER, content="Veux-tu parler ?"),),
            schema=Answer,
        )


async def test_a_client_counts_what_a_game_costs_in_calls_and_in_seconds() -> None:
    """The budget of a game is an acceptance criterion, not a curiosity (GL-7, J7.5.3)."""
    client = client_of(answering({"urgency": 10, "intention": "Oui."}))

    for _ in range(3):
        await client.complete(
            model="ministral-3b-latest",
            messages=(Message(role=Role.USER, content="Veux-tu parler ?"),),
            schema=Answer,
        )

    assert len(client.asked) == 3
    assert client.seconds_spent >= 0.0
    assert [asked.model for asked in client.asked] == ["ministral-3b-latest"] * 3
