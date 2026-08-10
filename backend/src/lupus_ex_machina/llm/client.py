"""A chat client that speaks the OpenAI protocol, and nothing else (D-043).

One client for every provider: Mistral is consumed through its OpenAI-compatible
endpoint, so there is no proprietary SDK anywhere in the project. D-034 asked for
one and was revoked for this reason.

The shape of an answer is imposed rather than hoped for (D-035): every request
carries the JSON schema of the model it expects, marked strict. The probe of
2026-08-03 confirmed Mistral honours it. Pydantic validates all the same — a
perfectly valid JSON can still ask to vote for a dead player, and the engine
remains the last authority on that (D-001).

Prompts and the contents of messages are French, because they are read by the
models; everything around them is English (HR-6).
"""

import asyncio
import json
import time
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import httpx2
from pydantic import ValidationError

from lupus_ex_machina.llm.backoff import RetryPolicy
from lupus_ex_machina.llm.completions import Answer, Asked
from lupus_ex_machina.llm.errors import ModelAnswerError, ThrottledError
from lupus_ex_machina.llm.messages import Message, Role

#: Asked once more, and only once: a model that will not comply on the second
#: attempt costs a turn, not a game. Any higher and a badly written prompt would
#: quietly multiply the budget of a whole game (GL-7).
ATTEMPTS = 2

#: What the provider answers when a quota is spent. The one status worth waiting
#: out: everything else is wrong rather than early.
TOO_MANY_REQUESTS = 429

#: How the client waits. Injected so the suite never actually sleeps.
Sleep = Callable[[float], Awaitable[None]]


class ChatClient:
    """A conversation endpoint, and the one place a request is built."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        transport: httpx2.AsyncBaseTransport | None = None,
        timeout: float = 60.0,
        sleep: Sleep = asyncio.sleep,
        retries: RetryPolicy | None = None,
    ) -> None:
        """Take where to call, what to call with, and how long to wait for it.

        The transport and the sleeping are injectable so the whole suite runs
        offline and instantly: a test answers in place of the provider rather
        than reaching one, and collects the waits rather than taking them (GL-2).
        """
        self._client = httpx2.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=timeout,
        )
        self._sleep = sleep
        self._retries = retries if retries is not None else RetryPolicy()
        self.asked: list[Asked] = []
        self.seconds_spent = 0.0

    @property
    def retries(self) -> RetryPolicy:
        """How this client waits out a provider that says there are too many.

        Readable like :attr:`asked` and :attr:`seconds_spent`: a policy that
        could only be checked by waiting through it could not be checked at all.
        """
        return self._retries

    async def complete(
        self,
        *,
        model: str,
        messages: Sequence[Message],
        schema: type[Answer],
        temperature: float = 1.0,
        top_p: float = 1.0,
    ) -> Answer:
        """Ask a model for one answer of that shape, and hand it back validated.

        An answer that does not fit is put back to the model **with what was
        wrong with it**, once. Telling it is the whole point: a model asked
        again with the same prompt tends to answer the same thing.

        Every request is counted, and the time it took with it: what a game
        costs in calls and in seconds is an acceptance criterion of this jalon,
        not something to find out afterwards (GL-7).
        """
        self.asked.append(
            Asked(
                model=model,
                messages=tuple(messages),
                schema_name=schema.__name__,
                temperature=temperature,
                top_p=top_p,
            )
        )
        started = time.monotonic()
        try:
            return await self._answered(
                model=model,
                messages=messages,
                schema=schema,
                temperature=temperature,
                top_p=top_p,
            )
        finally:
            self.seconds_spent += time.monotonic() - started

    async def _answered(
        self,
        *,
        model: str,
        messages: Sequence[Message],
        schema: type[Answer],
        temperature: float,
        top_p: float,
    ) -> Answer:
        """Ask, validate, and ask once more with the error when it does not fit."""
        conversation = list(messages)
        errors: list[str] = []

        for _ in range(ATTEMPTS):
            answered = await self._ask(
                model=model,
                messages=conversation,
                schema=schema,
                temperature=temperature,
                top_p=top_p,
            )
            try:
                return schema.model_validate_json(answered)
            except ValidationError as invalid:
                errors.append(str(invalid))
                conversation = [*conversation, *self._correction(answered, invalid)]

        raise ModelAnswerError(
            f"{model} did not answer with a valid {schema.__name__} in {ATTEMPTS} attempts: "
            f"{errors[-1]}"
        )

    @staticmethod
    def _correction(answered: str, invalid: ValidationError) -> tuple[Message, Message]:
        """What the model answered, and what was wrong with it.

        Both, in order: an error on its own leaves the model guessing which of
        its fields it is about.
        """
        return (
            Message(role=Role.ASSISTANT, content=answered),
            Message(
                role=Role.USER,
                content=(
                    "Ta réponse ne respecte pas le format demandé. "
                    f"Erreurs : {invalid}. Réponds à nouveau, en JSON valide uniquement."
                ),
            ),
        )

    async def _ask(
        self,
        *,
        model: str,
        messages: Sequence[Message],
        schema: type[Answer],
        temperature: float,
        top_p: float,
    ) -> str:
        """Send one request, waiting out a provider that says there are too many.

        Only a spent quota is waited out: an unknown model or a refused key is
        wrong rather than early, and retrying it would spend a minute finding
        out the same thing again.
        """
        body = self._body(
            model=model, messages=messages, schema=schema, temperature=temperature, top_p=top_p
        )
        response = await self._client.post("/chat/completions", json=body)

        for delay in self._retries.delays():
            if response.status_code != TOO_MANY_REQUESTS:
                break
            await self._sleep(_asked_for(response, instead_of=delay))
            response = await self._client.post("/chat/completions", json=body)

        if response.status_code == TOO_MANY_REQUESTS:
            raise ThrottledError(f"{model} kept refusing after {self._retries.attempts} attempts")

        response.raise_for_status()
        answered: str = response.json()["choices"][0]["message"]["content"]
        return answered

    @staticmethod
    def _body(
        *,
        model: str,
        messages: Sequence[Message],
        schema: type[Answer],
        temperature: float,
        top_p: float,
    ) -> dict[str, Any]:
        """The request one completion is, as the OpenAI protocol describes it."""
        return {
            "model": model,
            "messages": [json.loads(message.model_dump_json()) for message in messages],
            "temperature": temperature,
            "top_p": top_p,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "schema": schema.model_json_schema(),
                    "strict": True,
                },
            },
        }


def _asked_for(response: httpx2.Response, *, instead_of: float) -> float:
    """The wait the provider asked for, or the one the policy had in mind (D-047).

    Its own answer wins: the provider knows when the quota comes back, the
    policy is only guessing.
    """
    header = response.headers.get("Retry-After")
    if header is None:
        return instead_of
    try:
        return float(header)
    except ValueError:
        return instead_of
