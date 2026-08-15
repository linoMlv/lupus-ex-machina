"""Letting a provider into the registry, once it has answered (D-115).

The light probe of the two: is the key good, does the URL answer. It is the
listing of :mod:`lupus_ex_machina.providers.catalogue` and nothing more — the
smallest request the protocol has, and one that spends no tokens. Somebody
fixing a typo in a URL should not pay for a generation to find out (GL-7).

**It cannot prove that a model will play**, and does not pretend to. A provider
hosts many models, some of which honour a strict JSON schema and some of which
do not, so that question is asked of each model at its first use and lives in
:mod:`lupus_ex_machina.providers.compatibility` (D-115).
"""

import httpx2

from lupus_ex_machina.providers.catalogue import Catalogue, ProviderUnreachable, offered_by
from lupus_ex_machina.providers.registry import ProviderRegistry


async def admitted(
    name: str,
    *,
    base_url: str,
    api_key: str,
    registry: ProviderRegistry,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> Catalogue:
    """Probe that provider and keep it if it answered.

    The catalogue comes back either way, which is what the screen adding a
    provider shows next: the models it may now give to a seat, or why there are
    none. Kept **only** on an answer — a registry of endpoints that do not
    answer is a list of entries nobody can play on.

    A missing secret raises out of the registry rather than being answered here
    (D-113). It is not a fact about the provider: nothing is wrong with it, the
    server simply has nowhere safe to put its key, and that refusal already
    names what to set.
    """
    catalogue = await offered_by(base_url, api_key=api_key, transport=transport)
    if isinstance(catalogue, ProviderUnreachable):
        return catalogue
    registry.remember(name, base_url=base_url, api_key=api_key)
    return catalogue
