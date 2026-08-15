"""What a provider offers, asked of the provider itself (D-112).

The models a seat may be given are not written down anywhere in this project:
they are whatever the provider answers when asked, over the listing of the
OpenAI protocol every entry of the registry speaks (D-043). Nothing here is
specific to one provider — that is the whole reason D-034 was revoked.

Separate from :mod:`lupus_ex_machina.llm.client` on purpose: talking *to* a model
and asking a provider *which* models it has are two different conversations, and
only the first has anything to do with prompts, schemas or spent quotas.
"""

from typing import Any

import httpx2
from pydantic import BaseModel, ConfigDict

from lupus_ex_machina.providers.registry import ProviderRegistry
from lupus_ex_machina.providers.vault import UnreadableSecretError

#: Where an OpenAI-compatible provider lists what it offers.
MODELS_PATH = "/models"

#: How long a listing is waited for. Far shorter than the minute a completion is
#: given: this one is a cheap call behind a settings screen, and a wrong URL that
#: takes a minute to say so makes that screen unusable.
TIMEOUT_SECONDS = 10.0


class ModelsOffered(BaseModel):
    """The models a provider answered with, in a stable order."""

    model_config = ConfigDict(frozen=True)

    models: tuple[str, ...] = ()
    """Sorted, like the providers themselves: this list is read to pick a model
    for a seat, and one that reorders itself between two visits is read twice."""


class ProviderUnreachable(BaseModel):
    """Nothing could be listed, and why."""

    model_config = ConfigDict(frozen=True)

    reason: str
    """What to show whoever asked. French, like everything rendered on screen
    (HR-6), and it names the endpoint: a settings screen holds several, and a
    refusal that says only "unreachable" leaves the reader guessing which."""


#: What asking a provider for its models comes back as: the listing, or why
#: there is none. A union rather than one type with an empty list and a reason
#: beside it, like every other closed set on this project: a provider that
#: answered with nothing and one that never answered are two different things,
#: and a single shape would let a caller read one for the other.
Catalogue = ModelsOffered | ProviderUnreachable


async def offered_by(
    base_url: str,
    *,
    api_key: str,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> Catalogue:
    """Ask that provider what it offers, and come back either way.

    **Nothing raises out of here.** Whoever asks is a settings screen with a
    provider somebody has just typed in: a wrong URL, a mistyped key and a
    provider having a bad morning are ordinary answers to that question, not
    failures of this server (J8bis.2.2).

    The transport is injectable so the whole suite runs offline: a test answers
    in place of the provider rather than reaching one (GL-2).
    """
    try:
        response = await _asked(base_url, api_key=api_key, transport=transport)
        response.raise_for_status()
        return ModelsOffered(models=_named(response.json()))
    except httpx2.HTTPStatusError as refused:
        return ProviderUnreachable(
            reason=(
                f"{base_url} a refusé la demande (HTTP {refused.response.status_code}). "
                "Vérifiez la clé et l'URL de base du fournisseur."
            )
        )
    except httpx2.RequestError:
        return ProviderUnreachable(
            reason=(
                f"{base_url} n'a pas répondu. Vérifiez l'URL de base du fournisseur "
                "et l'accès au réseau."
            )
        )
    except (KeyError, TypeError, ValueError):
        return ProviderUnreachable(
            reason=(
                f"{base_url} a répondu, mais pas par une liste de modèles. "
                "Cette URL est-elle bien un endpoint compatible OpenAI ?"
            )
        )


async def catalogue_of(
    name: str,
    *,
    registry: ProviderRegistry,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> Catalogue:
    """Ask the provider of that name what it offers.

    By name, because nobody outside holds the key: it is handed over here and
    nowhere else (D-113).

    **Two troubles that look alike are treated as opposites.** A key this secret
    can no longer read is *answered* — it is a known state of the world, it has a
    remedy, and it belongs on screen beside the provider it concerns, exactly
    like the card that comes back without an ending (J8bis.1.5). A name that was
    never registered *raises*: nobody typed it, so the caller asked for something
    that does not exist, and answering it would show an empty list of models for
    a provider the screen invented.

    **The order of the two lines below is what keeps them apart**, not the guard:
    the lookup happens outside the ``try``, so no widening of that clause can
    ever swallow an unknown name.
    """
    base_url = registry.base_url_of(name)
    try:
        api_key = registry.key_of(name)
    except UnreadableSecretError as unreadable:
        return ProviderUnreachable(reason=str(unreadable))
    return await offered_by(base_url, api_key=api_key, transport=transport)


async def _asked(
    base_url: str,
    *,
    api_key: str,
    transport: httpx2.AsyncBaseTransport | None,
) -> httpx2.Response:
    """Put the listing request to that provider."""
    async with httpx2.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}"},
        transport=transport,
        timeout=TIMEOUT_SECONDS,
    ) as client:
        return await client.get(MODELS_PATH)


def _named(listing: dict[str, Any]) -> tuple[str, ...]:
    """The names in that listing, sorted.

    Anything but a listing raises out of here — a missing ``data``, an entry
    without an ``id``, a body that is not an object at all — and is caught by
    :func:`offered_by` as the answer it is.
    """
    return tuple(sorted(str(offered["id"]) for offered in listing["data"]))
