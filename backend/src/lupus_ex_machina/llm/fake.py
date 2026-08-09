"""A provider that answers without a network (GL-2).

The rules of the game are exercised by scripted agents; the *models* are
exercised by this. It answers from a script when it has one, and invents an
answer when it does not — a whole game asks far more questions than a script can
reasonably hold.

It also keeps every request it was handed, which is what makes a prompt testable:
a test reads here what would have been sent, rather than trusting that it was
built correctly (J7.2.6).
"""

from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel, ValidationError

from lupus_ex_machina.llm.completions import Answer, Asked
from lupus_ex_machina.llm.errors import ModelAnswerError
from lupus_ex_machina.llm.messages import Message

#: How an answer is made up once the script has run out. Takes what was asked —
#: the schema and the conversation — and answers the raw JSON a model would.
Inventor = Callable[[type[BaseModel], Sequence[Message]], str]


class NothingToAnswerError(RuntimeError):
    """The fake was asked something with no script left and no way to invent."""


class FakeCompletions:
    """A provider whose answers a test decides."""

    def __init__(self, *, script: Sequence[str] = (), invent: Inventor | None = None) -> None:
        """Take the answers to give, and how to make up the ones after them."""
        self._script = list(script)
        self._invent = invent
        self.asked: list[Asked] = []
        self.seconds_spent = 0.0
        """Nothing, and truthfully so: answering from a script reaches nobody."""

    async def complete(
        self,
        *,
        model: str,
        messages: Sequence[Message],
        schema: type[Answer],
        temperature: float = 1.0,
        top_p: float = 1.0,
    ) -> Answer:
        """Answer as a provider would, and validate it as strictly as the real one.

        Validated rather than trusted: a fake that accepted what a provider
        would not would hide the very bug it exists to catch.
        """
        self.asked.append(
            Asked(
                model=model,
                messages=tuple(messages),
                schema_name=schema.__name__,
                temperature=temperature,
                top_p=top_p,
            )
        )
        answered = self._answer(schema, messages)
        try:
            return schema.model_validate_json(answered)
        except ValidationError as invalid:
            raise ModelAnswerError(
                f"the fake answered no valid {schema.__name__}: {invalid}"
            ) from (invalid)

    def _answer(self, schema: type[Any], messages: Sequence[Message]) -> str:
        """The next scripted answer, or one made up, or a loud failure."""
        if self._script:
            return self._script.pop(0)
        if self._invent is not None:
            return self._invent(schema, messages)
        raise NothingToAnswerError(
            f"nothing left to answer a {schema.__name__} with: "
            "give the fake a script or an inventor"
        )
