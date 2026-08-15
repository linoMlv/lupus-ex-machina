"""The providers a table may play on, and the keys that open them (D-112).

What replaces the single key of the environment. Several providers, each an
OpenAI-compatible endpoint and nothing more (D-043), so that a seat can bid on
the cheap model of one and speak with the capable model of another (D-114).

The environment keeps its own key all the same: ``make play-llm`` must stay
playable without a server or any stored state, which is what makes it a way of
checking things (GL-2).
"""

from lupus_ex_machina.providers.admission import admitted
from lupus_ex_machina.providers.cards import ProviderCard
from lupus_ex_machina.providers.catalogue import (
    Catalogue,
    ModelsOffered,
    ProviderUnreachable,
    catalogue_of,
)
from lupus_ex_machina.providers.compatibility import compatibility_of, probed
from lupus_ex_machina.providers.registry import (
    ProviderError,
    ProviderRegistry,
    UnknownProviderError,
)
from lupus_ex_machina.providers.verdicts import Verdict

__all__ = [
    "Catalogue",
    "ModelsOffered",
    "ProviderCard",
    "ProviderError",
    "ProviderRegistry",
    "ProviderUnreachable",
    "UnknownProviderError",
    "Verdict",
    "admitted",
    "catalogue_of",
    "compatibility_of",
    "probed",
]
