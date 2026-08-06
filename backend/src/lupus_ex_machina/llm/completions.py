"""What every provider of answers looks like, real or not.

One protocol so the rest of the project never knows which it is talking to: the
real client reaches a provider, the fake one answers from a script (GL-2). J8
leans on the same seam to run a whole game in a test.
"""

from collections.abc import Sequence
from typing import Protocol, TypeVar

from pydantic import BaseModel, ConfigDict

from lupus_ex_machina.llm.messages import Message

#: Answers are Pydantic models, and a provider hands back the type it was asked
#: for rather than a dictionary its caller would have to validate again.
Answer = TypeVar("Answer", bound=BaseModel)


class Asked(BaseModel):
    """One request a provider was handed, kept for whoever wants to count them.

    The budget of a game is an acceptance criterion (GL-7): how many calls it
    took, on which models, is read off the provider rather than tallied by every
    caller that cares.
    """

    model_config = ConfigDict(frozen=True)

    model: str
    messages: tuple[Message, ...]
    schema_name: str
    temperature: float
    top_p: float


class Completions(Protocol):
    """Something able to answer a conversation in a given shape."""

    @property
    def asked(self) -> Sequence[Asked]:
        """Every request this provider was handed, in order."""
        ...  # pragma: no cover - a Protocol body carries no behaviour

    async def complete(
        self,
        *,
        model: str,
        messages: Sequence[Message],
        schema: type[Answer],
        temperature: float = 1.0,
        top_p: float = 1.0,
    ) -> Answer:
        """Answer that conversation with an instance of that schema."""
        ...  # pragma: no cover - a Protocol body carries no behaviour
