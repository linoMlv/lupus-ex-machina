"""Keeping what a probe concluded, so it is paid for once (D-115, J8bis.3.3).

The compatibility probe costs a real generation. Asking it again at every game
would spend tokens to learn what is already known — but keeping the *wrong*
thing is worse: a provider having a bad minute would be condemned by it.
"""

import json
from pathlib import Path

import httpx2
import pytest

from lupus_ex_machina.providers.compatibility import compatibility_of
from lupus_ex_machina.providers.registry import ProviderRegistry, UnknownProviderError
from lupus_ex_machina.providers.verdicts import Verdict
from support.providers import (
    a_registry,
    a_registry_holding_mistral,
    completing,
    refusing,
)

ANSWERED_WELL = json.dumps({"understood": True})
OFF_SCHEMA = json.dumps({"whatever": "not the shape asked for"})

MODEL = "mistral-small-latest"


async def asked(
    registry: ProviderRegistry,
    *,
    transport: httpx2.MockTransport,
    model: str = MODEL,
) -> Verdict:
    """What is known of that model at the one provider these tests register."""
    return await compatibility_of(model, provider="mistral", registry=registry, transport=transport)


async def test_a_verdict_is_not_paid_for_twice(tmp_path: Path) -> None:
    registry = a_registry_holding_mistral(tmp_path)
    seen: list[httpx2.Request] = []

    first = await asked(registry, transport=completing(ANSWERED_WELL, seen=seen))
    second = await asked(registry, transport=completing(ANSWERED_WELL, seen=seen))

    assert (first, second) == (Verdict.COMPATIBLE, Verdict.COMPATIBLE)
    assert len(seen) == 1, "the second answer came from what was remembered"


async def test_a_verdict_survives_the_process_that_learnt_it(tmp_path: Path) -> None:
    """The point of writing it down: a game started tomorrow pays nothing."""
    await asked(a_registry_holding_mistral(tmp_path), transport=completing(ANSWERED_WELL))

    seen: list[httpx2.Request] = []
    verdict = await asked(a_registry(tmp_path), transport=completing(ANSWERED_WELL, seen=seen))

    assert verdict is Verdict.COMPATIBLE
    assert seen == []


async def test_registering_a_provider_again_forgets_what_was_learnt_of_it(
    tmp_path: Path,
) -> None:
    """The entry may now point somewhere else, and a verdict is about a model *there*.

    Re-probing a handful of models costs far less than seating one on a
    compatibility that belonged to another endpoint.
    """
    await asked(a_registry_holding_mistral(tmp_path), transport=completing(ANSWERED_WELL))

    registered_again = a_registry_holding_mistral(tmp_path)

    assert registered_again.verdict_on("mistral", "mistral-small-latest") is None


def test_writing_a_verdict_for_a_provider_nobody_kept_says_which(tmp_path: Path) -> None:
    """Named in the refusal, like every other way of asking for one that is not there.

    A provider can be removed between a probe being started and its verdict
    coming back.
    """
    with pytest.raises(UnknownProviderError, match="mistral"):
        a_registry(tmp_path).remember_verdict("mistral", "mistral-small-latest", Verdict.COMPATIBLE)


async def test_probing_a_model_at_a_provider_nobody_kept_says_which(tmp_path: Path) -> None:
    """Raised, exactly as asking that provider for its models is.

    Nothing is known of a model at an endpoint nobody registered — but answering
    "unknown" would let a caller keep probing a provider that does not exist,
    once per game, for ever.
    """
    with pytest.raises(UnknownProviderError, match="mistral"):
        await asked(a_registry(tmp_path), transport=completing(ANSWERED_WELL))


async def test_a_verdict_is_kept_by_model_and_not_by_provider(tmp_path: Path) -> None:
    """The trap of D-115: NIM hosts dozens of third-party models.

    Some honour the schema and some do not, so what was learnt of one says
    nothing of the next.
    """
    registry = a_registry_holding_mistral(tmp_path)

    await asked(registry, transport=completing(ANSWERED_WELL))
    another = await asked(registry, transport=completing(OFF_SCHEMA), model="some-other-model")

    assert another is Verdict.NEEDS_CONFIRMATION


async def test_a_confirmation_still_owed_is_remembered_too(tmp_path: Path) -> None:
    """It is something learnt, so it is kept.

    And it is what a settings screen has to show to ask the owner for their call
    (D-115).
    """
    registry = a_registry_holding_mistral(tmp_path)
    seen: list[httpx2.Request] = []

    first = await asked(registry, transport=completing(OFF_SCHEMA, seen=seen))
    second = await asked(registry, transport=completing(OFF_SCHEMA, seen=seen))

    assert (first, second) == (Verdict.NEEDS_CONFIRMATION, Verdict.NEEDS_CONFIRMATION)
    assert len(seen) == 1


async def test_nothing_learnt_is_nothing_kept(tmp_path: Path) -> None:
    """A spent quota must not condemn a model for ever (D-115).

    The question is simply asked again — which means asking it again costs a
    request.
    """
    registry = a_registry_holding_mistral(tmp_path)

    first = await asked(registry, transport=refusing(429))

    seen: list[httpx2.Request] = []
    second = await asked(registry, transport=completing(ANSWERED_WELL, seen=seen))

    assert first is Verdict.UNKNOWN
    assert second is Verdict.COMPATIBLE
    assert len(seen) == 1, "nothing was remembered, so the probe ran again"


async def test_a_provider_whose_key_cannot_be_read_teaches_nothing(tmp_path: Path) -> None:
    """No key, no probe — and nothing learnt about the model either way."""
    moved_on = a_registry_holding_mistral(tmp_path, secret="un-autre-secret")
    seen: list[httpx2.Request] = []

    verdict = await asked(moved_on, transport=completing(ANSWERED_WELL, seen=seen))

    assert verdict is Verdict.UNKNOWN
    assert seen == [], "nothing was ever sent: there was no key to send it with"
