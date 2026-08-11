"""Keeping the providers a table may play on (D-112).

The registry is what replaces the single key of the environment: several
providers, each an OpenAI-compatible endpoint (D-043), so that one seat can bid
on one and speak on another (D-114).
"""

from pathlib import Path

import pytest

from lupus_ex_machina.providers.registry import (
    ProviderRegistry,
    UnknownProviderError,
)
from lupus_ex_machina.providers.vault import UnreadableSecretError

MISTRAL = "https://api.mistral.ai/v1"
NIM = "https://integrate.api.nvidia.com/v1"


def a_registry(tmp_path: Path) -> ProviderRegistry:
    """A registry of its own, on a file that does not exist yet."""
    return ProviderRegistry(tmp_path / "providers.json", secret="clef-de-chiffrement")


def test_a_registry_starts_empty(tmp_path: Path) -> None:
    assert a_registry(tmp_path).names() == ()


def test_a_provider_is_kept_and_found_again(tmp_path: Path) -> None:
    registry = a_registry(tmp_path)

    registry.remember("mistral", base_url=MISTRAL, api_key="sk-abcd1234")

    assert registry.names() == ("mistral",)
    assert registry.key_of("mistral") == "sk-abcd1234"


def test_providers_are_listed_in_a_stable_order(tmp_path: Path) -> None:
    """Sorted rather than left to insertion: a list that wanders reorders itself."""
    registry = a_registry(tmp_path)

    registry.remember("nim", base_url=NIM, api_key="nvapi-2222")
    registry.remember("mistral", base_url=MISTRAL, api_key="sk-1111")

    assert registry.names() == ("mistral", "nim")


def test_registering_the_same_name_again_replaces_it(tmp_path: Path) -> None:
    """Editing a provider is what saving over it *is* — the alternative is two."""
    registry = a_registry(tmp_path)

    registry.remember("mistral", base_url=MISTRAL, api_key="sk-old")
    registry.remember("mistral", base_url=MISTRAL, api_key="sk-new")

    assert registry.names() == ("mistral",)
    assert registry.key_of("mistral") == "sk-new"


def test_a_provider_is_forgotten_when_asked(tmp_path: Path) -> None:
    registry = a_registry(tmp_path)
    registry.remember("mistral", base_url=MISTRAL, api_key="sk-abcd1234")

    registry.forget("mistral")

    assert registry.names() == ()


def test_forgetting_one_that_was_never_there_says_so(tmp_path: Path) -> None:
    with pytest.raises(UnknownProviderError, match="mistral"):
        a_registry(tmp_path).forget("mistral")


def test_asking_for_a_provider_that_was_never_there_says_which(tmp_path: Path) -> None:
    """Named in the refusal: a seat may point at a provider somebody has removed."""
    with pytest.raises(UnknownProviderError, match="mistral"):
        a_registry(tmp_path).key_of("mistral")

    with pytest.raises(UnknownProviderError, match="mistral"):
        a_registry(tmp_path).base_url_of("mistral")


def test_what_was_kept_survives_the_process_that_kept_it(tmp_path: Path) -> None:
    """The point of a file: a provider registered yesterday is there today."""
    a_registry(tmp_path).remember("mistral", base_url=MISTRAL, api_key="sk-abcd1234")

    reopened = a_registry(tmp_path)

    assert reopened.names() == ("mistral",)
    assert reopened.base_url_of("mistral") == MISTRAL


def test_what_the_outside_is_shown_carries_no_key(tmp_path: Path) -> None:
    """D-113: a card recognises a key, it does not hand it over."""
    registry = a_registry(tmp_path)
    registry.remember("mistral", base_url=MISTRAL, api_key="sk-abcd1234")

    (card,) = registry.cards()

    assert (card.name, card.base_url, card.key_ending) == ("mistral", MISTRAL, "1234")
    assert "sk-abcd1234" not in card.model_dump_json()


def test_a_secret_that_has_changed_is_said_rather_than_swallowed(tmp_path: Path) -> None:
    """Otherwise the symptom looks like the provider rejecting a good key."""
    a_registry(tmp_path).remember("mistral", base_url=MISTRAL, api_key="sk-abcd1234")

    with_another = ProviderRegistry(tmp_path / "providers.json", secret="un-autre-secret")

    with pytest.raises(UnreadableSecretError, match="LUPUS_SECRET_KEY"):
        with_another.key_of("mistral")


def test_a_secret_that_has_changed_leaves_the_rest_of_the_registry_alone(tmp_path: Path) -> None:
    """One unreadable key must not take the whole settings screen down with it."""
    a_registry(tmp_path).remember("mistral", base_url=MISTRAL, api_key="sk-abcd1234")

    with_another = ProviderRegistry(tmp_path / "providers.json", secret="un-autre-secret")

    assert with_another.names() == ("mistral",)
    assert with_another.base_url_of("mistral") == MISTRAL

    (card,) = with_another.cards()
    assert card.key_ending is None, "an unreadable key is said, never shown as a blank one"


def test_a_key_is_never_written_down_in_the_clear(tmp_path: Path) -> None:
    """D-113: whoever reads the file gets nothing they can call a provider with."""
    registry = a_registry(tmp_path)
    registry.remember("mistral", base_url=MISTRAL, api_key="sk-abcd1234")

    on_disk = (tmp_path / "providers.json").read_text(encoding="utf-8")

    assert "sk-abcd1234" not in on_disk
    assert "mistral" in on_disk, "the name is not a secret, and the file must be readable at all"
