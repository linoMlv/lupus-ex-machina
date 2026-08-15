"""Asking for the models of a provider the registry keeps (D-112, D-113).

The half a settings screen actually calls: a **name**, not a URL and a key.
Nobody outside holds either — the key is handed over inside the registry and
nowhere else — so asking by name is what keeps it there.
"""

from pathlib import Path

import httpx2
import pytest

from lupus_ex_machina.providers.catalogue import ModelsOffered, ProviderUnreachable, catalogue_of
from lupus_ex_machina.providers.registry import ProviderRegistry, UnknownProviderError
from support.providers import (
    API_KEY,
    MISTRAL,
    SECRET,
    a_registry_holding_mistral,
    answering,
    offering,
)


async def test_a_registered_provider_is_asked_at_its_own_endpoint_with_its_own_key(
    tmp_path: Path,
) -> None:
    seen: list[httpx2.Request] = []

    catalogue = await catalogue_of(
        "mistral",
        registry=a_registry_holding_mistral(tmp_path),
        transport=answering(offering("mistral-small-latest"), seen=seen),
    )

    assert catalogue == ModelsOffered(models=("mistral-small-latest",))
    (asked,) = seen
    assert str(asked.url) == f"{MISTRAL}/models"
    assert asked.headers["Authorization"] == f"Bearer {API_KEY}"


async def test_a_provider_whose_secret_has_changed_is_told_rather_than_raised(
    tmp_path: Path,
) -> None:
    """One provider whose key can no longer be read must not take the screen down.

    Same arbitration as the card without an ending (J8bis.1.5): the trouble is
    known, named, and belongs on screen — not in a stack trace.
    """
    moved_on = a_registry_holding_mistral(tmp_path, secret="un-autre-secret")

    catalogue = await catalogue_of("mistral", registry=moved_on, transport=answering(offering()))

    assert isinstance(catalogue, ProviderUnreachable)
    assert "LUPUS_SECRET_KEY" in catalogue.reason


async def test_asking_for_a_provider_that_was_never_registered_says_which(
    tmp_path: Path,
) -> None:
    """Raised rather than answered, unlike everything else here.

    A provider that is not in the registry is not a provider having a bad
    morning: nobody typed it, so the caller asked for something that does not
    exist, and swallowing that would show an empty list of models for a name the
    screen invented.
    """
    empty = ProviderRegistry(tmp_path / "providers.json", secret=SECRET)

    with pytest.raises(UnknownProviderError, match="mistral"):
        await catalogue_of("mistral", registry=empty, transport=answering(offering()))
