"""Building the client a game is played by, from where it calls and how it waits.

Two sources, and they are not the same one. *Where* to call comes from the
environment — a key and a base URL nobody puts in a game (D-090). *How to wait*
comes from the game itself, because the retry policy is a setting of the
configuration (D-092).

Which is why this takes both, and why a provider is built when a game is dealt
rather than when the server starts: at start-up there is no game yet, so there
is no policy to build it with, and a client built too early would fall back on
its own defaults — the exact defect J8.0 was opened to repair.
"""

from collections.abc import Callable

from lupus_ex_machina.config import Settings
from lupus_ex_machina.configuration.system import SystemOptions
from lupus_ex_machina.llm.backoff import retries_for
from lupus_ex_machina.llm.client import ChatClient
from lupus_ex_machina.llm.throttling import Waiting

#: How a client is obtained once the game it will play is known, and once there
#: is somebody to tell that it is waiting (D-066).
Provider = Callable[[SystemOptions, Waiting], ChatClient]


def provider_for(settings: Settings) -> Provider | None:
    """How to build a client from these settings, or nothing when there is no key.

    A *way* of building rather than a client, because the two halves arrive at
    different times: the key at start-up, the retry policy when a game is dealt.
    Whoever holds this can answer "can we play at all" long before there is a
    game to play (D-090).
    """
    if settings.llm_api_key is None:
        return None
    key = settings.llm_api_key

    def built(system: SystemOptions, waiting: Waiting) -> ChatClient:
        return ChatClient(
            base_url=settings.llm_base_url,
            api_key=key,
            retries=retries_for(system),
            waiting=waiting,
        )

    return built


def configured_provider(settings: Settings, system: SystemOptions) -> ChatClient | None:
    """The client those settings describe for that game, or nothing (D-090).

    Building it reaches nobody — a client is a base URL and a header until it is
    asked something — which is what lets the wiring be tested without a network.
    """
    build = provider_for(settings)
    return build(system, _nobody_to_tell) if build is not None else None


def _nobody_to_tell(seconds: float) -> None:
    """Where a wait goes when nothing is watching — the console command (J7)."""
