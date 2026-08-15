"""Whether a model honours a strict JSON schema, asked of the model (D-115).

The heavy probe of the two. It costs a real generation, which is why it is run
at a model's **first use** and its verdict kept afterwards — and why the light
probe of :mod:`lupus_ex_machina.providers.admission` does not try to answer this
question when a provider is added. Compatibility is a property of a **model**,
not of a provider: an endpoint hosting dozens of third-party models hosts some
that honour the schema and some that do not.

**A failed probe does not prove an incompatibility**, and that is the whole
subject. Three observations, three different things learnt:

===================================== ==========================================
The provider names the parameter      it will not take → a refusal, stated by
                                      the only party in a position to state it
It answers, off-schema                → the owner's call, so confirmation asked
Anything else                         → nothing learnt; ask again another time
===================================== ==========================================
"""

import httpx2
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lupus_ex_machina.llm.messages import Message, Role
from lupus_ex_machina.llm.requests import completion_body
from lupus_ex_machina.providers.registry import ProviderRegistry
from lupus_ex_machina.providers.vault import UnreadableSecretError
from lupus_ex_machina.providers.verdicts import Verdict

#: Where an OpenAI-compatible provider answers a conversation.
COMPLETIONS_PATH = "/chat/completions"

#: How long a probe is waited for. As long as a real completion, because that is
#: what it is: a model asked to generate, on the smallest question there is.
TIMEOUT_SECONDS = 60.0

#: How an endpoint says it will not take a parameter. Both are in use — 400 by
#: the letter of HTTP, 422 by the habit of frameworks that validate bodies.
REFUSAL_STATUSES = frozenset({400, 422})

#: What a refusal has to name for it to count as one. Anything less is a four
#: hundred that could mean twenty other things (D-115).
THE_PARAMETER = ("response_format", "json_schema")

#: The smallest question worth asking. French, like everything a model reads
#: (HR-6), and short enough that probing costs a handful of tokens (GL-7).
QUESTION = "Réponds au format demandé, sans rien ajouter."


class ProbeAnswer(BaseModel):
    """The shape a probe asks for: one field, and nothing besides.

    Closed to unknown fields like every answer of the project, so that a model
    that adds its own commentary fails the schema rather than passing (D-035).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    understood: bool = Field(description="Réponds simplement vrai.")


async def probed(
    model: str,
    *,
    base_url: str,
    api_key: str,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> Verdict:
    """Ask that model to answer a strict schema, and read what happened.

    Nothing raises out of here: every way this can go wrong is one of the four
    verdicts, and three of them are ways of learning nothing in particular.
    """
    try:
        response = await _asked(model, base_url=base_url, api_key=api_key, transport=transport)
    except httpx2.RequestError:
        return Verdict.UNKNOWN

    if _is_a_stated_refusal(response):
        return Verdict.REFUSED
    if response.status_code != httpx2.codes.OK:
        return Verdict.UNKNOWN
    return _read(response)


async def compatibility_of(
    model: str,
    *,
    provider: str,
    registry: ProviderRegistry,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> Verdict:
    """What is known of that model at that provider, probing only if nothing is.

    Kept afterwards, because the probe costs a real generation and the answer
    does not change on its own (D-115). **Except when nothing was learnt**: an
    :attr:`Verdict.UNKNOWN` is not written down, so a spent quota costs one
    wasted request rather than condemning a model until somebody notices.

    A key this secret can no longer read teaches nothing either — there is no
    probe to run — and the trouble is the registry's to report, not the model's
    to be blamed for.
    """
    remembered = registry.verdict_on(provider, model)
    if remembered is not None:
        return remembered

    try:
        api_key = registry.key_of(provider)
    except UnreadableSecretError:
        return Verdict.UNKNOWN

    verdict = await probed(
        model,
        base_url=registry.base_url_of(provider),
        api_key=api_key,
        transport=transport,
    )
    if verdict is not Verdict.UNKNOWN:
        registry.remember_verdict(provider, model, verdict)
    return verdict


def _is_a_stated_refusal(response: httpx2.Response) -> bool:
    """Whether the provider named the parameter it will not take.

    Both halves are needed. A four hundred on its own can be a malformed
    request, an unknown model, or a provider having a bad day: reading it as an
    incompatibility would throw away a good provider for a reason nobody stated.
    """
    if response.status_code not in REFUSAL_STATUSES:
        return False
    said = response.text.lower()
    return any(parameter in said for parameter in THE_PARAMETER)


def _read(response: httpx2.Response) -> Verdict:
    """What a two hundred turns out to be worth."""
    try:
        answered: str = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError):
        return Verdict.UNKNOWN

    try:
        ProbeAnswer.model_validate_json(answered)
    except ValidationError:
        return Verdict.NEEDS_CONFIRMATION
    return Verdict.COMPATIBLE


async def _asked(
    model: str,
    *,
    base_url: str,
    api_key: str,
    transport: httpx2.AsyncBaseTransport | None,
) -> httpx2.Response:
    """Put the probe to that model, as a game would put a real turn.

    The body is built by the same code the client builds its own with: a probe
    that assembled its own would be checking a request nobody ever sends.
    """
    body = completion_body(
        model=model,
        messages=(Message(role=Role.USER, content=QUESTION),),
        schema=ProbeAnswer,
    )
    async with httpx2.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}"},
        transport=transport,
        timeout=TIMEOUT_SECONDS,
    ) as client:
        return await client.post(COMPLETIONS_PATH, json=body)
