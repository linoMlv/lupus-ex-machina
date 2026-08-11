"""The providers a table may play on, and the keys that open them (D-112).

What replaces the single key of the environment. Several providers, each an
OpenAI-compatible endpoint and nothing more (D-043), so that a seat can bid on
the cheap model of one and speak with the capable model of another (D-114).

The environment keeps its own key all the same: ``make play-llm`` must stay
playable without a server or any stored state, which is what makes it a way of
checking things (GL-2).
"""

from lupus_ex_machina.providers.registry import (
    ProviderCard,
    ProviderError,
    ProviderRegistry,
    UnknownProviderError,
)

__all__ = [
    "ProviderCard",
    "ProviderError",
    "ProviderRegistry",
    "UnknownProviderError",
]
