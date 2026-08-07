"""The scripted cast the role scenarios are played by, one agent per situation."""

from collections.abc import Sequence

from lupus_ex_machina.agents.scripted import Scripted
from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.events import (
    Event,
)
from lupus_ex_machina.engine.intents import (
    IntentKind,
    PriorityPoint,
    RoleAction,
    SharePriority,
    TakeTurn,
    Vote,
    Wait,
)
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleActionName, RoleName
from lupus_ex_machina.engine.turn import Turn
from lupus_ex_machina.engine.views import PlayerView

# Agents built for one scenario each.


class HuntsFirst(Scripted):
    """A wolf that always puts its whole budget on the lowest-seated prey."""

    async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
        """Bid flatly: what this agent is for is what it does with the floor."""
        return Bid(urgency=50, intention="Jouer.")

    async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
        """Weigh the first prey, otherwise stay out of the way."""
        if IntentKind.SHARE_PRIORITY in view.allowed_intents and view.action_targets:
            return Turn(
                intent=SharePriority(
                    allocations=(
                        PriorityPoint(target=view.action_targets[0], points=view.priority_budget),
                    )
                )
            )
        if view.may_vote:
            return Turn(intent=TakeTurn(vote=Vote()))
        return Turn(intent=Wait())


class AimsAt(Scripted):
    """Someone who fires at a named player, and otherwise keeps quiet."""

    def __init__(self, target: PlayerId) -> None:
        """Take the player this agent will shoot when it gets the chance."""
        self._target = target

    async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
        """Bid flatly: what this agent is for is what it does with the floor."""
        return Bid(urgency=50, intention="Jouer.")

    async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
        """Shoot the named player, otherwise vote blank or wait."""
        if RoleActionName.SHOOT in view.available_actions and self._target in view.action_targets:
            return Turn(intent=RoleAction(action=RoleActionName.SHOOT, target=self._target))
        if view.may_vote:
            return Turn(intent=TakeTurn(vote=Vote()))
        return Turn(intent=Wait())


PACK = PlayerId("w0")

WITCH = PlayerId("w1")

PREY = PlayerId("v2")

OTHER_PREY = PlayerId("v3")

A_TABLE_WITH_A_WITCH = (
    Player(id=PACK, name="Adèle", seat=0, role=RoleName.WEREWOLF),
    Player(id=WITCH, name="Basile", seat=1, role=RoleName.WITCH),
    Player(id=PREY, name="Camille", seat=2, role=RoleName.VILLAGER),
    Player(id=OTHER_PREY, name="Diane", seat=3, role=RoleName.VILLAGER),
)
