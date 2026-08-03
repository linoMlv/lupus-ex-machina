"""The contract between the engine and whoever plays.

A scripted agent and a language model agent are interchangeable because both
answer the same question: given what you are allowed to know, what do you want
to do? (D-001)

The engine never trusts the answer — it validates it — which is what lets a
model be plugged in later without weakening the rules.
"""

from typing import Protocol, runtime_checkable

from lupus_ex_machina.engine.intents import Intent
from lupus_ex_machina.engine.views import PlayerView


@runtime_checkable
class Agent(Protocol):
    """Something able to play a seat."""

    def decide(self, view: PlayerView) -> Intent:
        """Return what this player wants to do, given what they know."""
        ...  # pragma: no cover - a Protocol body carries no behaviour
