"""The contract between the engine and whoever plays.

A scripted agent and a language model agent are interchangeable because both
answer the same question: given what you are allowed to know, what do you want
to do? (D-001)

The engine never trusts the answer — it validates it — which is what lets a
model be plugged in later without weakening the rules.

Both answers are awaited (D-087). A scripted agent has nothing to wait for and
returns at once; a model answers over a network, and the whole table is asked
for its bid in one go rather than one after another (GL-7).
"""

from typing import Protocol, runtime_checkable

from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.turn import Turn
from lupus_ex_machina.engine.views import PlayerView


@runtime_checkable
class Agent(Protocol):
    """Something able to play a seat."""

    async def bid(self, view: PlayerView) -> Bid:
        """Return how badly this player wants the floor right now (D-002).

        Asked far more often than :meth:`decide` — once per player per turn at
        the floor — so it is the call a game spends most of its budget on, and
        the one that has to stay short (GL-7).
        """
        ...  # pragma: no cover - a Protocol body carries no behaviour

    async def decide(self, view: PlayerView) -> Turn:
        """Return this player's whole turn: what they made of it, and what they do.

        The three parts come back together because they are one thought, and
        because each round trip to a model costs (D-004, GL-7).
        """
        ...  # pragma: no cover - a Protocol body carries no behaviour
