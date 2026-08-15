"""Providers that answer in place of a real one, and never over the network.

Every test of the provider package answers through a mock transport, which is
what keeps the suite free, fast and offline (GL-2). What is under test is the
request the project builds and what it makes of the answer — never the provider.
"""

from pathlib import Path
from typing import Any

import httpx2

from lupus_ex_machina.providers.registry import ProviderRegistry

MISTRAL = "https://api.mistral.ai/v1"
API_KEY = "sk-abcd1234"
SECRET = "clef-de-chiffrement"


def answering(payload: object, *, seen: list[httpx2.Request] | None = None) -> httpx2.MockTransport:
    """A transport that always answers with that payload, keeping the requests."""

    def respond(request: httpx2.Request) -> httpx2.Response:
        if seen is not None:
            seen.append(request)
        return httpx2.Response(200, json=payload)

    return httpx2.MockTransport(respond)


def offering(*names: str) -> dict[str, Any]:
    """What an OpenAI-compatible endpoint answers when asked for its models."""
    return {"object": "list", "data": [{"id": name, "object": "model"} for name in names]}


def failing(raised: Exception) -> httpx2.MockTransport:
    """A transport that never gets an answer back, the way a network does not."""

    def fail(request: httpx2.Request) -> httpx2.Response:
        raise raised

    return httpx2.MockTransport(fail)


def refusing(status: int, *, saying: str = "nope") -> httpx2.MockTransport:
    """A transport whose provider answers, but refuses — in its own words.

    What it says matters for the compatibility probe: a provider that names the
    parameter it will not take is refusing the schema, one that says something
    else is refusing for a reason the probe cannot read (D-115).
    """
    return httpx2.MockTransport(
        lambda request: httpx2.Response(status, json={"error": {"message": saying}})
    )


def completing(content: str, *, seen: list[httpx2.Request] | None = None) -> httpx2.MockTransport:
    """A transport whose provider answers a completion with that raw content."""

    def respond(request: httpx2.Request) -> httpx2.Response:
        if seen is not None:
            seen.append(request)
        return httpx2.Response(200, json={"choices": [{"message": {"content": content}}]})

    return httpx2.MockTransport(respond)


def a_registry(tmp_path: Path, *, secret: str | None = SECRET) -> ProviderRegistry:
    """A registry on that directory's file — empty until something is kept in it.

    Opening it a second time is how a restart is written: same file, same
    secret, a registry that remembers nothing of the object before it.
    """
    return ProviderRegistry(tmp_path / "providers.json", secret=secret)


def a_registry_holding_mistral(tmp_path: Path, *, secret: str = SECRET) -> ProviderRegistry:
    """A registry with one provider in it, read back under that secret.

    It **registers** the provider, which clears anything learnt of its models —
    use :func:`a_registry` to reopen one without touching what it holds.
    """
    ProviderRegistry(tmp_path / "providers.json", secret=SECRET).remember(
        "mistral", base_url=MISTRAL, api_key=API_KEY
    )
    return ProviderRegistry(tmp_path / "providers.json", secret=secret)
