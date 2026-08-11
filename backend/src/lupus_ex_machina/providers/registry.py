"""The providers this installation knows, and where their keys are kept.

One JSON file rather than a directory of them, unlike the template library of J6
(D-068): a registry holds a handful of entries and is always read whole, so a
file per provider would multiply the reads without buying anything back.

**A key never leaves this module in the clear.** What the outside asks for is a
:class:`ProviderCard`, which carries the name, the endpoint and the last four
characters — enough to recognise a key, useless to anybody who copies it. The
key itself is handed over only to whoever is about to call the provider with it.
"""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.providers.vault import UnreadableSecretError, opened, sealed

ENCODING = "utf-8"

#: How much of a key is shown back. Four characters is what a person recognises
#: their own key by, and what nobody can do anything with.
SHOWN_CHARACTERS = 4


class ProviderError(Exception):
    """Something the registry could not be asked to do."""


class UnknownProviderError(ProviderError):
    """No provider of that name was ever registered."""


class NoSecretError(ProviderError):
    """A key was offered with no secret to keep it under (D-113).

    Refused rather than stored under a secret drawn at start-up: that would
    encrypt the registry with something the next restart no longer has, and the
    keys would be lost without anybody being told.
    """


class ProviderCard(BaseModel):
    """A provider as the outside is allowed to see it (D-113).

    Never the key. A form filled in with the stored secret "for convenience" is
    the ordinary way a settings screen leaks one: the value travels in the
    response and nobody notices, the screen showing dots.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    base_url: str
    key_ending: str | None = Field(
        default=None,
        description="The last characters of the key, to recognise it by.",
    )
    """Absent when the key cannot be read at all — the secret has changed since
    it was stored, or there is none. Said rather than left blank: a screen that
    showed nothing would look like a provider registered without a key, and the
    person would never think to enter it again."""


class ProviderRegistry:
    """The providers of this installation, kept between runs."""

    def __init__(self, path: Path, *, secret: str | None) -> None:
        """Hold the file providers live in, and the secret their keys are kept under.

        The file is created when first written to, like the template library:
        an installation that has registered nothing has nothing to read.

        The secret may be missing, and the registry still works for everything
        that is not a key: names and endpoints are no secret, so a settings
        screen keeps showing what is registered and says why it can add nothing.
        """
        self._path = path
        self._secret = secret

    def names(self) -> tuple[str, ...]:
        """Every provider registered, in a stable order.

        Sorted rather than left to insertion: an order that wanders makes a list
        that reorders itself between two visits.
        """
        return tuple(sorted(self._kept()))

    def cards(self) -> tuple[ProviderCard, ...]:
        """What the outside may be shown of every provider (D-113)."""
        kept = self._kept()
        return tuple(self._card(name, kept[name]) for name in sorted(kept))

    def remember(self, name: str, *, base_url: str, api_key: str) -> None:
        """Keep that provider, replacing any of the same name.

        Saving over is what editing a provider *is*; the alternative is two
        entries of one name disagreeing about a key.
        """
        secret = self._sealing_secret()
        kept = self._kept()
        kept[name] = {"base_url": base_url, "api_key": sealed(api_key, secret=secret)}
        self._write(kept)

    def forget(self, name: str) -> None:
        """Remove that provider."""
        kept = self._kept()
        if name not in kept:
            raise UnknownProviderError(f"Le fournisseur « {name} » est introuvable")
        del kept[name]
        self._write(kept)

    def base_url_of(self, name: str) -> str:
        """Where that provider answers."""
        return self._entry(name)["base_url"]

    def key_of(self, name: str) -> str:
        """The key that opens that provider, in the clear.

        Handed over only here, and only to whoever is about to call with it.
        Raises :class:`UnreadableSecretError` when the secret has changed since
        the key was stored — said out loud, never returned as an empty key.
        """
        return opened(self._entry(name)["api_key"], secret=self._sealing_secret())

    # --- The file ---------------------------------------------------------

    def _sealing_secret(self) -> str:
        """The secret keys are kept under, or a refusal naming what to set."""
        if self._secret is None:
            raise NoSecretError(
                "Aucun secret pour chiffrer les clés : renseignez LUPUS_SECRET_KEY "
                "dans l'environnement, puis redémarrez le serveur."
            )
        return self._secret

    def _entry(self, name: str) -> dict[str, str]:
        """One provider, or a refusal naming it."""
        kept = self._kept()
        if name not in kept:
            raise UnknownProviderError(f"Le fournisseur « {name} » est introuvable")
        return kept[name]

    def _card(self, name: str, entry: dict[str, str]) -> ProviderCard:
        """That entry, with the key reduced to what it is recognised by.

        The ending comes from the key **in the clear**: the tail of the stored
        ciphertext is the tail of a base64 blob, which recognises nothing.

        An unreadable key gives a card without an ending rather than no card at
        all — one provider whose secret has moved on must not take the settings
        screen down with it.
        """
        return ProviderCard(
            name=name,
            base_url=entry["base_url"],
            key_ending=self._ending_of(entry["api_key"]),
        )

    def _ending_of(self, stored: str) -> str | None:
        """The last characters of that key, or nothing when it cannot be read."""
        if self._secret is None:
            return None
        try:
            return opened(stored, secret=self._secret)[-SHOWN_CHARACTERS:]
        except UnreadableSecretError:
            return None

    def _kept(self) -> dict[str, dict[str, str]]:
        """Everything on file, or nothing at all."""
        if not self._path.is_file():
            return {}
        written: dict[str, dict[str, str]] = json.loads(self._path.read_text(encoding=ENCODING))
        return written

    def _write(self, kept: dict[str, dict[str, str]]) -> None:
        """Put the whole registry back, creating its directory if need be."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(kept, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding=ENCODING,
        )
