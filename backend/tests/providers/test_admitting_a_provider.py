"""The light probe, run when a provider is added (D-115, J8bis.3.1).

Is the key good, does the URL answer. Nothing more is asked at this point: what
a provider can *do* is a question about each of its models, and one this probe
is in no position to answer (D-115).
"""

from pathlib import Path

import httpx2

from lupus_ex_machina.providers.admission import admitted
from lupus_ex_machina.providers.catalogue import ModelsOffered, ProviderUnreachable
from support.providers import (
    API_KEY,
    MISTRAL,
    a_registry,
    answering,
    failing,
    offering,
    refusing,
)


async def test_a_provider_that_answers_is_registered_with_its_models(tmp_path: Path) -> None:
    registry = a_registry(tmp_path)

    admission = await admitted(
        "mistral",
        base_url=MISTRAL,
        api_key=API_KEY,
        registry=registry,
        transport=answering(offering("mistral-small-latest")),
    )

    assert admission == ModelsOffered(models=("mistral-small-latest",))
    assert registry.names() == ("mistral",)
    assert registry.key_of("mistral") == API_KEY


async def test_the_probe_is_the_smallest_request_there_is(tmp_path: Path) -> None:
    """One listing, and no completion.

    A probe that generated something would spend real tokens every time somebody
    fixes a typo in a URL, and would still prove nothing about the models a seat
    is given three screens later (D-115, GL-7).
    """
    seen: list[httpx2.Request] = []

    await admitted(
        "mistral",
        base_url=MISTRAL,
        api_key=API_KEY,
        registry=a_registry(tmp_path),
        transport=answering(offering(), seen=seen),
    )

    (asked,) = seen
    assert asked.method == "GET"
    assert str(asked.url) == f"{MISTRAL}/models"


async def test_a_provider_that_cannot_be_reached_is_not_registered(tmp_path: Path) -> None:
    """Nothing is kept.

    A registry of endpoints that do not answer is a screen full of entries
    nobody can play on.
    """
    registry = a_registry(tmp_path)

    admission = await admitted(
        "mistral",
        base_url=MISTRAL,
        api_key=API_KEY,
        registry=registry,
        transport=failing(httpx2.ConnectError("nowhere to connect")),
    )

    assert isinstance(admission, ProviderUnreachable)
    assert registry.names() == ()


async def test_a_key_the_provider_refuses_is_not_registered_either(tmp_path: Path) -> None:
    """The mistyped key, which is what this probe exists for (D-115)."""
    registry = a_registry(tmp_path)

    admission = await admitted(
        "mistral",
        base_url=MISTRAL,
        api_key="sk-mistyped",
        registry=registry,
        transport=refusing(401),
    )

    assert isinstance(admission, ProviderUnreachable)
    assert "401" in admission.reason
    assert registry.names() == ()
