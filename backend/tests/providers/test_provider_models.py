"""Asking an OpenAI-compatible endpoint what models it offers (D-112, D-043).

The conversation with the endpoint itself: what request is built, what is made
of the answer, and what becomes of an answer that never comes. Asking for the
models of a provider the registry *keeps* is the other half, and lives in
``test_models_of_a_registered_provider``.
"""

import httpx2

from lupus_ex_machina.providers.catalogue import ModelsOffered, ProviderUnreachable, offered_by
from support.providers import API_KEY, MISTRAL, answering, failing, offering, refusing


async def test_the_models_a_provider_offers_come_back_named() -> None:
    catalogue = await offered_by(
        MISTRAL,
        api_key=API_KEY,
        transport=answering(offering("ministral-3b-latest", "mistral-small-latest")),
    )

    assert catalogue == ModelsOffered(models=("ministral-3b-latest", "mistral-small-latest"))


async def test_the_request_goes_to_the_models_endpoint_carrying_the_key() -> None:
    """The standard listing of the protocol, with the key the registry keeps."""
    seen: list[httpx2.Request] = []

    await offered_by(MISTRAL, api_key=API_KEY, transport=answering(offering(), seen=seen))

    (asked,) = seen
    assert str(asked.url) == f"{MISTRAL}/models"
    assert asked.headers["Authorization"] == f"Bearer {API_KEY}"


async def test_models_come_back_in_a_stable_order() -> None:
    """Sorted, like the providers themselves.

    A list that wanders reorders itself between two visits, and this one is read
    to pick a model for a seat.
    """
    catalogue = await offered_by(
        MISTRAL,
        api_key=API_KEY,
        transport=answering(offering("mistral-small-latest", "codestral-latest")),
    )

    assert catalogue == ModelsOffered(models=("codestral-latest", "mistral-small-latest"))


async def test_a_provider_that_offers_nothing_is_not_a_failure() -> None:
    """An empty catalogue is an answer: the provider replied, it offers nothing.

    Told apart from a provider that could not be reached, which is why the two
    are two shapes rather than one with an empty list in it.
    """
    catalogue = await offered_by(MISTRAL, api_key=API_KEY, transport=answering(offering()))

    assert catalogue == ModelsOffered(models=())


# --- When the provider does not answer with a listing (J8bis.2.2) -------------


async def test_a_provider_that_cannot_be_reached_is_told_rather_than_raised() -> None:
    """A settings screen must come back with a reason, not with a stack trace."""
    catalogue = await offered_by(
        MISTRAL, api_key=API_KEY, transport=failing(httpx2.ConnectError("nowhere to connect"))
    )

    assert isinstance(catalogue, ProviderUnreachable)
    assert MISTRAL in catalogue.reason


async def test_a_refused_key_comes_back_as_a_reason_naming_the_status() -> None:
    """401 is the ordinary answer to a key that was mistyped.

    The status is what tells that apart from a provider that is down: worth
    reading, so worth carrying.
    """
    catalogue = await offered_by(MISTRAL, api_key=API_KEY, transport=refusing(401))

    assert isinstance(catalogue, ProviderUnreachable)
    assert "401" in catalogue.reason
    assert MISTRAL in catalogue.reason


async def test_an_answer_that_is_not_json_at_all_is_told_rather_than_raised() -> None:
    """The ordinary typing mistake.

    The address of a website rather than of an API, which answers a perfectly
    good page of HTML.
    """
    serving_a_page = httpx2.MockTransport(
        lambda request: httpx2.Response(200, html="<html><body>Bienvenue</body></html>")
    )

    catalogue = await offered_by(MISTRAL, api_key=API_KEY, transport=serving_a_page)

    assert isinstance(catalogue, ProviderUnreachable)
    assert MISTRAL in catalogue.reason


async def test_an_answer_that_is_not_a_listing_is_told_rather_than_raised() -> None:
    """A 200 carrying something else is not a listing either.

    An endpoint that is not the one we think, or a provider whose protocol has
    drifted from the one it claims.
    """
    catalogue = await offered_by(MISTRAL, api_key=API_KEY, transport=answering({"object": "list"}))

    assert isinstance(catalogue, ProviderUnreachable)
    assert MISTRAL in catalogue.reason
