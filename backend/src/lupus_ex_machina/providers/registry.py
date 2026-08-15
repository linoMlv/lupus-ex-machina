"""The providers this installation knows, and where their keys are kept.

What the registry *offers*; what it looks like on disk is
:mod:`lupus_ex_machina.providers.storage`.

**A key never leaves this module in the clear.** What the outside asks for is a
:class:`ProviderCard`, which carries the name, the endpoint and the last four
characters — enough to recognise a key, useless to anybody who copies it. The
key itself is handed over only to whoever is about to call the provider with it.
"""

from pathlib import Path

from lupus_ex_machina.providers.cards import ProviderCard, card_of
from lupus_ex_machina.providers.storage import Entry, read_from, write_to
from lupus_ex_machina.providers.vault import opened, sealed
from lupus_ex_machina.providers.verdicts import Verdict


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
        return tuple(card_of(name, kept[name], secret=self._secret) for name in sorted(kept))

    def remember(self, name: str, *, base_url: str, api_key: str) -> None:
        """Keep that provider, replacing any of the same name.

        Saving over is what editing a provider *is*; the alternative is two
        entries of one name disagreeing about a key.

        **What was learnt of its models does not survive the replacement**: the
        entry may now point at another endpoint, and a verdict is about a model
        *there*. Re-probing a handful of models costs far less than seating one
        on a compatibility somebody else's endpoint once had.
        """
        secret = self._sealing_secret()
        kept = self._kept()
        kept[name] = Entry(base_url=base_url, api_key=sealed(api_key, secret=secret))
        self._write(kept)

    def verdict_on(self, name: str, model: str) -> Verdict | None:
        """What a probe concluded of that model there, or nothing yet (D-115).

        Nothing is also the answer for a provider that is not registered: asking
        what is known of a model at an endpoint nobody kept is answered by "not
        a thing", which is true, rather than by a refusal the caller would have
        to guard against before every probe.
        """
        kept = self._kept()
        if name not in kept:
            return None
        return kept[name].verdicts.get(model)

    def remember_verdict(self, name: str, model: str, verdict: Verdict) -> None:
        """Write down what was learnt of that model there.

        Refuses, naming the provider, when there is none of that name: one can
        be removed while a probe is in flight, and a verdict filed against
        nothing would come back as a key error three layers up.
        """
        entry = self._entry(name)
        kept = self._kept()
        kept[name] = entry.model_copy(update={"verdicts": {**entry.verdicts, model: verdict}})
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
        return self._entry(name).base_url

    def key_of(self, name: str) -> str:
        """The key that opens that provider, in the clear.

        Handed over only here, and only to whoever is about to call with it.
        Raises :class:`UnreadableSecretError` when the secret has changed since
        the key was stored — said out loud, never returned as an empty key.
        """
        return opened(self._entry(name).api_key, secret=self._sealing_secret())

    # --- The file ---------------------------------------------------------

    def _sealing_secret(self) -> str:
        """The secret keys are kept under, or a refusal naming what to set."""
        if self._secret is None:
            raise NoSecretError(
                "Aucun secret pour chiffrer les clés : renseignez LUPUS_SECRET_KEY "
                "dans l'environnement, puis redémarrez le serveur."
            )
        return self._secret

    def _entry(self, name: str) -> Entry:
        """One provider, or a refusal naming it."""
        kept = self._kept()
        if name not in kept:
            raise UnknownProviderError(f"Le fournisseur « {name} » est introuvable")
        return kept[name]

    def _kept(self) -> dict[str, Entry]:
        """Everything on file, or nothing at all."""
        return read_from(self._path)

    def _write(self, kept: dict[str, Entry]) -> None:
        """Put the whole registry back."""
        write_to(self._path, kept)
