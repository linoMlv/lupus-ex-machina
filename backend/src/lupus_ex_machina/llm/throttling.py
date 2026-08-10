"""Getting a request through a provider that says there have been too many.

Split out of the client when it outgrew its plafond (HR-7), along the line its
own docstring drew: speaking the OpenAI protocol is one thing, surviving a spent
quota is another, and only the second has anything to do with waiting.

Two rules live here, and neither is about the shape of a request. **Only a spent
quota is waited out** — an unknown model or a refused key is wrong rather than
early, and retrying it would spend a minute discovering the same thing again.
And **the provider's own answer wins**: it knows when the quota comes back, the
policy is only guessing (D-047).
"""

from collections.abc import Awaitable, Callable
from typing import Any

import httpx2

from lupus_ex_machina.llm.backoff import RetryPolicy

#: What the provider answers when a quota is spent. The one status worth waiting
#: out: everything else is wrong rather than early.
TOO_MANY_REQUESTS = 429

#: Sending one request, however the caller does that.
Send = Callable[[dict[str, Any]], Awaitable[httpx2.Response]]

#: How the waiting is done. Injected so the suite never actually sleeps.
Sleep = Callable[[float], Awaitable[None]]

#: Somebody told, before each wait, how long it is about to be (D-066). A wait
#: nobody announces is a scene that stops with nothing on screen to explain it.
Waiting = Callable[[float], None]


async def sent_through(
    send: Send,
    body: dict[str, Any],
    *,
    retries: RetryPolicy,
    sleep: Sleep,
    waiting: Waiting | None = None,
) -> httpx2.Response:
    """Send it, waiting out a provider that says there are too many."""
    response = await send(body)

    for delay in retries.delays():
        if response.status_code != TOO_MANY_REQUESTS:
            break
        await _waited(_asked_for(response, instead_of=delay), sleep=sleep, waiting=waiting)
        response = await send(body)

    return response


async def _waited(seconds: float, *, sleep: Sleep, waiting: Waiting | None) -> None:
    """Wait that long, having said so first.

    Said before rather than after: an indicator that appears once the wait is
    over indicates nothing (D-066).
    """
    if waiting is not None:
        waiting(seconds)
    await sleep(seconds)


def _asked_for(response: httpx2.Response, *, instead_of: float) -> float:
    """The wait the provider asked for, or the one the policy had in mind (D-047).

    Its own answer wins: the provider knows when the quota comes back, the
    policy is only guessing. A header worded rather than counted — an HTTP date
    — falls back on the policy, because a game must not stop over a header.
    """
    header = response.headers.get("Retry-After")
    if header is None:
        return instead_of
    try:
        return float(header)
    except ValueError:
        return instead_of
