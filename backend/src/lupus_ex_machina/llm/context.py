"""What a model may be handed at once, and what is dropped when it is too much.

D-063 in three steps: each model declares its **real** window in the
configuration, a margin turns that into a budget, and nothing is ever pruned
until a conversation exceeds it. A model nobody declared a window for is never
pruned at all — a guessed window would cut a context that fitted, and nothing at
the table would explain why an agent had stopped remembering.

In practice this never fires in V1: a whole game is around fifteen thousand
tokens against windows of a hundred thousand and more. The mechanism is here
because D-063 is not satisfied by a measurement alone, and because it stays
correct if the word limits or the size of the table change.

The estimate is an estimate. No tokeniser is exact across providers, and
shipping one would be a dependency for arithmetic that the margin already
absorbs — being monotonic and roughly right is what the budget needs of it.
"""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from lupus_ex_machina.configuration.system import SystemOptions
from lupus_ex_machina.engine.events import Event, SpeechDelivered
from lupus_ex_machina.llm.messages import Message

#: Roughly what one token is worth in characters of French prose. Deliberately
#: on the low side: an estimate that under-counts would prune too late, which is
#: the failure that loses a call rather than a few old lines.
CHARACTERS_PER_TOKEN = 4

#: How many days of talk a pruned journal keeps in full (D-089). Two, because a
#: player argues about what was said yesterday and today; what is older, they
#: remember through their notebook.
DAYS_KEPT_IN_FULL = 2


def estimated_tokens(text: str) -> int:
    """About how many tokens that text is worth."""
    return len(text) // CHARACTERS_PER_TOKEN


class ContextBudget(BaseModel):
    """How much of a model's window one conversation may take up (D-063)."""

    model_config = ConfigDict(frozen=True)

    tokens: int | None = None
    """The ceiling, or ``None`` for a model whose window was never declared."""

    def holds(self, conversation: Sequence[Message]) -> bool:
        """Whether that whole conversation fits.

        Weighed whole rather than prompt by prompt: what fills a window is
        everything sent, standing instructions included.
        """
        if self.tokens is None:
            return True
        return sum(estimated_tokens(message.content) for message in conversation) <= self.tokens


def budget_for(model: str, options: SystemOptions) -> ContextBudget:
    """The budget that model is held to, from the window declared for it."""
    window = options.context_windows.get(model)
    if window is None:
        return ContextBudget()
    return ContextBudget(tokens=int(window * options.context_margin))


def pruned(journal: Sequence[Event], *, day: int) -> tuple[Event, ...]:
    """The same journal with the talk of the older days dropped (D-089).

    Deterministic, and no model is asked anything: an elision can be proved by
    mutation and played offline (GL-2), where a generated summary would be a
    call nobody ever exercises and whose quality no test can judge.

    **What goes is the talk, and only the talk.** It is the one thing that grows
    without bound — a hundred and twenty-five turns of fifty words over a game —
    while everything else a journal holds is a handful of facts: who died, what
    the table decided, what this player wrote down. Those stay however old they
    are, because they are what the game *is* rather than what was said about it.

    The notebook stays whole for a harder reason: it is replayed from these very
    facts (D-088), so dropping one would not shorten a prompt, it would make an
    agent forget a note it never deleted.
    """
    oldest_kept = day - DAYS_KEPT_IN_FULL + 1
    return tuple(
        event
        for event in journal
        if not (isinstance(event.payload, SpeechDelivered) and event.day < oldest_kept)
    )
