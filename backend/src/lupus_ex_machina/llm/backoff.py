"""How long to wait when a provider says there have been too many requests.

The first step is deliberately short (D-066). A long one empties the display
buffer that hides the latency of the models, and the scene freezes with nothing
on screen to explain why — the wait has to be visible to the player (J8), not
merely survived.

After that the wait doubles up to a ceiling, then stays there (D-047): a
provider that is still refusing after a minute is not going to relent because it
was asked more politely.
"""

from collections.abc import Iterator

from pydantic import BaseModel, ConfigDict, Field


class RetryPolicy(BaseModel):
    """What to do about a request a provider refused for rate reasons."""

    model_config = ConfigDict(frozen=True)

    first_delay_seconds: float = Field(
        default=1.0,
        gt=0.0,
        description="Première attente après un refus pour cause de débit dépassé.",
    )
    maximum_delay_seconds: float = Field(
        default=60.0,
        gt=0.0,
        description="Attente maximale entre deux tentatives, une fois le doublement arrêté.",
    )
    attempts: int = Field(
        default=8,
        ge=1,
        description="Nombre de tentatives avant d'abandonner la requête.",
    )

    def delays(self) -> Iterator[float]:
        """The waits between attempts, doubling up to the ceiling then holding.

        One fewer than there are attempts: nobody waits after the last one.
        """
        delay = self.first_delay_seconds
        for _ in range(self.attempts - 1):
            yield min(delay, self.maximum_delay_seconds)
            delay = min(delay * 2, self.maximum_delay_seconds)
