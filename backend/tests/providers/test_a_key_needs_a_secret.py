"""Refusing to store a key there is no secret to store it under (D-113).

The same variable carries two different demands, and that is the whole of this
module. ``LUPUS_SECRET_KEY`` signs the session cookie, where D-098 lets it be
missing: a key is drawn at start-up and everyone is logged out on a restart,
which costs nothing.

A registry cannot do that. Encrypted under a drawn key, it would be
**unreadable** at the next restart — so a key is refused rather than stored
under a secret that will not survive the process.
"""

from pathlib import Path

import pytest

from lupus_ex_machina.config import Settings
from lupus_ex_machina.providers.registry import NoSecretError, ProviderRegistry

MISTRAL = "https://api.mistral.ai/v1"


def test_a_key_is_refused_when_there_is_no_secret_to_seal_it_with(tmp_path: Path) -> None:
    registry = ProviderRegistry(tmp_path / "providers.json", secret=None)

    with pytest.raises(NoSecretError, match="LUPUS_SECRET_KEY"):
        registry.remember("mistral", base_url=MISTRAL, api_key="sk-abcd1234")


def test_nothing_is_written_when_a_key_is_refused(tmp_path: Path) -> None:
    """A refusal that left a file behind would be half a registration."""
    path = tmp_path / "providers.json"
    registry = ProviderRegistry(path, secret=None)

    with pytest.raises(NoSecretError):
        registry.remember("mistral", base_url=MISTRAL, api_key="sk-abcd1234")

    assert not path.exists()


def test_a_registry_without_a_secret_still_lists_what_is_there(tmp_path: Path) -> None:
    """Reading names is not reading keys: the screen still shows what is registered."""
    ProviderRegistry(tmp_path / "providers.json", secret="clef").remember(
        "mistral", base_url=MISTRAL, api_key="sk-abcd1234"
    )

    assert ProviderRegistry(tmp_path / "providers.json", secret=None).names() == ("mistral",)


def test_without_a_secret_a_card_says_the_key_cannot_be_read(tmp_path: Path) -> None:
    """The settings screen still opens, and says what is wrong rather than lying."""
    ProviderRegistry(tmp_path / "providers.json", secret="clef").remember(
        "mistral", base_url=MISTRAL, api_key="sk-abcd1234"
    )

    (card,) = ProviderRegistry(tmp_path / "providers.json", secret=None).cards()

    assert (card.name, card.base_url) == ("mistral", MISTRAL)
    assert card.key_ending is None


def test_a_supplied_secret_is_told_apart_from_a_drawn_one() -> None:
    """What the registry rests on: settings that say whether anybody chose a key."""
    assert Settings(secret_key="choisie").secret_key == "choisie"
    assert Settings().secret_key is None


def test_the_cookie_is_signed_either_way() -> None:
    """D-098 is untouched: absent, the session key is drawn and login still works."""
    drawn = Settings()

    assert drawn.session_key, "a cookie is always signable"
    assert drawn.session_key == drawn.session_key, "and stable for the life of the process"
    assert Settings(secret_key="choisie").session_key == "choisie"
