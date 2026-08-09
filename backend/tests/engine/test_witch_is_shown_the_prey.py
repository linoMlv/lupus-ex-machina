"""The witch is shown what the pack settled on, whenever it settled (D-029, D-081)."""

from collections.abc import Sequence

from lupus_ex_machina.agents.scripted import Scripted, SilentAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.events import (
    Event,
    NightPowerUsed,
    PackRunoffOpened,
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
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.roles import RoleActionName
from lupus_ex_machina.engine.rules import GameRules, NightOptions
from lupus_ex_machina.engine.runner.game import open_the_game
from lupus_ex_machina.engine.runner.night import play_night
from lupus_ex_machina.engine.runner.scribe import Scribe
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.turn import Turn
from lupus_ex_machina.engine.views import PlayerView
from support.scenarios import (
    A_TABLE_WITH_A_WITCH,
    OTHER_PREY,
    PACK,
    PREY,
    WITCH,
)

# --- The witch is shown what the pack settled on, whenever it settled --------


class SavesWhoeverIsShown(Scripted):
    """A witch who pours her potion of life on the victim she is shown (D-029)."""

    async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
        """Never asks for the floor: this seat is here for its potion."""
        return Bid(urgency=0, intention="Rien à dire.")

    async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
        """Heal the prey the night shows her, if it shows her one."""
        if RoleActionName.HEAL in view.available_actions and view.victim_tonight is not None:
            return Turn(intent=RoleAction(action=RoleActionName.HEAL, target=view.victim_tonight))
        return Turn(intent=TakeTurn(vote=Vote()) if view.may_vote else Wait())


class SplitsThenSettles(Scripted):
    """A wolf that ties the pack on the first round, then names one prey.

    A single wolf splitting its budget evenly is the simplest way to reach the
    tie the runoff exists for: two prey worth exactly the same.
    """

    def __init__(self) -> None:
        """Start before the first round of the pack's vote."""
        self._has_split = False

    async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
        """Say nothing: the pack's channel is not what this test is about."""
        return Bid(urgency=0, intention="Rien à dire.")

    async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
        """Split the budget evenly, then name one prey when asked a second time."""
        if IntentKind.SHARE_PRIORITY not in view.allowed_intents or not view.action_targets:
            return Turn(intent=TakeTurn(vote=Vote()) if view.may_vote else Wait())

        prey = view.action_targets
        if self._has_split:
            return Turn(
                intent=SharePriority(allocations=(PriorityPoint(target=prey[0], points=100),))
            )

        self._has_split = True
        return Turn(
            intent=SharePriority(
                allocations=tuple(PriorityPoint(target=one, points=50) for one in prey[:2])
            )
        )


async def test_the_witch_is_shown_the_prey_a_runoff_settled_on() -> None:
    """D-029 has to hold however the pack got there.

    Woken before the pack's tie was broken, she would be shown nobody, keep her
    potion, and watch the runoff kill someone she could have saved. The order of
    the night says she comes after the pack; that has to mean after it has
    *finished*, runoff and all.
    """
    state = GameState.initial(A_TABLE_WITH_A_WITCH)
    agents: dict[PlayerId, Agent] = {
        PACK: SplitsThenSettles(),
        WITCH: SavesWhoeverIsShown(),
        PREY: SilentAgent(),
        OTHER_PREY: SilentAgent(),
    }
    journal = Journal()
    scribe = Scribe(agents, journal, create_rng(5))
    opened = scribe.enter(open_the_game(scribe, state), Phase.DAY, day=1)

    await play_night(scribe, scribe.enter(opened, Phase.RESOLUTION))

    healed = [
        event.payload
        for event in journal.events
        if isinstance(event.payload, NightPowerUsed) and event.payload.action is RoleActionName.HEAL
    ]

    assert healed, "the witch was shown a victim and answered the bite"


async def test_a_pack_whose_tie_is_never_put_back_takes_nobody() -> None:
    """The night's runoff is a setting too (D-050), and this is what it costs.

    Without it, the same split pack leaves the night empty-handed: nobody is
    asked again, and a tie is the final word.
    """
    settled_at_once = GameRules(night=NightOptions(hold_a_runoff_on_a_tie=False))
    state = GameState.initial(A_TABLE_WITH_A_WITCH, rules=settled_at_once)
    agents: dict[PlayerId, Agent] = {
        PACK: SplitsThenSettles(),
        WITCH: SavesWhoeverIsShown(),
        PREY: SilentAgent(),
        OTHER_PREY: SilentAgent(),
    }
    journal = Journal()
    scribe = Scribe(agents, journal, create_rng(5))
    opened = scribe.enter(open_the_game(scribe, state), Phase.DAY, day=1)

    closed, _ = await play_night(scribe, scribe.enter(opened, Phase.RESOLUTION))

    assert not [event for event in journal.events if isinstance(event.payload, PackRunoffOpened)]
    assert len(closed.living) == len(A_TABLE_WITH_A_WITCH), "a tie spares everyone at once"
