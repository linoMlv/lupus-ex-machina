"""A game is played by the rules it was configured with, everywhere.

This is the property J5 closed without: ``_validate_healing`` asked the night
what the witch could see while handing it a *default* policy instead of the one
the game was set up with. The view made the same call, so the two agreed with
each other and disagreed with the game — the quietest kind of wrong.

The fix is structural rather than careful: the rules live in the state, so no
caller can supply the wrong ones or forget to supply any. That is the same
argument ``runoff_targets`` is in the state for — a view derived from the state
alone cannot be told about a restriction only the caller knew.
"""

from collections.abc import Sequence

import pytest

from lupus_ex_machina.agents.scripted import RandomAgent, Scripted
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.bidding import Bid, elect
from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.events import (
    Event,
    ForcedVoteReason,
    RoleRevealed,
    SpeechDelivered,
    VoteForced,
)
from lupus_ex_machina.engine.intents import (
    IntentKind,
    PriorityPoint,
    RoleAction,
    SharePriority,
    TakeTurn,
    Wait,
)
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.night import night_callers
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.roles import RoleActionName, RoleName
from lupus_ex_machina.engine.rules import (
    DebateOptions,
    GameRules,
    InformationOptions,
    NightOptions,
    RoleOptions,
    TableOptions,
    VoteOptions,
)
from lupus_ex_machina.engine.runner import GameDidNotEndError, play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.turn import Turn
from lupus_ex_machina.engine.validation import validate_intent
from lupus_ex_machina.engine.views import PlayerView, project

WOLF = PlayerId("p0")
WITCH = PlayerId("p1")
SEER = PlayerId("p2")
VILLAGER = PlayerId("p3")
OTHER_VILLAGER = PlayerId("p4")

TABLE = (
    Player(id=WOLF, name="Adèle", seat=0, role=RoleName.WEREWOLF),
    Player(id=WITCH, name="Basile", seat=1, role=RoleName.WITCH),
    Player(id=SEER, name="Camille", seat=2, role=RoleName.SEER),
    Player(id=VILLAGER, name="Diane", seat=3, role=RoleName.VILLAGER),
    Player(id=OTHER_VILLAGER, name="Émile", seat=4, role=RoleName.VILLAGER),
)

FORCED = GameRules(night=NightOptions(require_werewolf_target=True))


def night_of(rules: GameRules) -> GameState:
    """A game played by those rules, on the night of its first day."""
    return (
        GameState.initial(TABLE, rules=rules)
        .entering(Phase.DAY, day=1)
        .entering(Phase.RESOLUTION)
        .entering(Phase.NIGHT)
    )


def test_a_game_carries_the_rules_it_is_played_by() -> None:
    """Handed to the state once, rather than to every function that reads them."""
    assert night_of(FORCED).rules == FORCED
    assert GameState.initial(TABLE).rules == GameRules()


def test_the_witch_is_shown_the_prey_the_lot_drew_for_the_pack() -> None:
    """The open point of J5, closed: the view reads the game's own rules.

    Under ``require_werewolf_target`` the prey is drawn rather than named
    (D-081). A view built from default rules shows the witch nothing, and she
    keeps a potion of life while the game kills someone she was never shown.
    """
    state = night_of(FORCED).with_prey_drawn(VILLAGER)

    assert project(state, WITCH).victim_tonight == VILLAGER


def test_the_validator_lets_the_witch_heal_the_prey_the_lot_drew() -> None:
    """And the validator reads them too, so it accepts what the view offered.

    The two must agree by construction. Reading the same field of the same state
    is what makes that true without a test having to watch over it.
    """
    state = night_of(FORCED).with_prey_drawn(VILLAGER)

    validate_intent(state, WITCH, RoleAction(action=RoleActionName.HEAL, target=VILLAGER))


def test_a_pack_that_names_its_prey_is_read_the_same_way_by_both() -> None:
    """The ordinary path, kept honest alongside the drawn one."""
    state = night_of(GameRules()).with_priority_share_from(
        WOLF, (PriorityPoint(target=VILLAGER, points=100),)
    )

    assert project(state, WITCH).victim_tonight == VILLAGER
    validate_intent(state, WITCH, RoleAction(action=RoleActionName.HEAL, target=VILLAGER))


# --- One option of each category, proven observable (J6.3.2) -----------------
#
# A field of the schema that changes nothing is a lie in the form of J11. These
# are the six categories the engine reads; agents, display and system are read
# by J7, J10 and J11, and are proven there.


def test_the_table_deals_the_number_of_seats_it_was_configured_with() -> None:
    """Catégorie Partie."""
    six = create_game(GameRules(table=TableOptions(player_count=6)))

    assert len(six.players) == 6
    assert len(create_game().players) == 8


def test_a_witch_forbidden_from_saving_herself_is_refused_that_potion() -> None:
    """Catégorie Rôles: D-029 lets her; the option is the classic handicap."""
    selfless = GameRules(roles=RoleOptions(witch_may_save_herself=False))
    state = night_of(selfless).with_priority_share_from(
        WOLF, (PriorityPoint(target=WITCH, points=100),)
    )

    with pytest.raises(IllegalIntentError):
        validate_intent(state, WITCH, RoleAction(action=RoleActionName.HEAL, target=WITCH))

    # Her other potion still reaches everyone else, so what has to go is herself.
    assert WITCH not in project(state, WITCH).action_targets, "and the view stops offering it"


def test_a_witch_allowed_to_save_herself_may_pour_the_potion_on_herself() -> None:
    """The other half of the same option, so neither branch is untested."""
    state = night_of(GameRules()).with_priority_share_from(
        WOLF, (PriorityPoint(target=WITCH, points=100),)
    )

    validate_intent(state, WITCH, RoleAction(action=RoleActionName.HEAL, target=WITCH))
    assert WITCH in project(state, WITCH).action_targets


async def test_a_game_that_reveals_nothing_records_no_revelation() -> None:
    """Catégorie Information et visibilité."""
    silent = GameRules(information=InformationOptions(reveal_role_on_death=False))

    assert await _revelations_in(silent) == 0
    assert await _revelations_in(GameRules()) > 0, "and the default does reveal"


async def _revelations_in(rules: GameRules) -> int:
    state = create_game(rules, rng=create_rng(3))
    agents: dict[PlayerId, Agent] = {
        player.id: RandomAgent(rng=create_rng(3)) for player in state.players
    }
    result = await play_game(state, agents, journal=Journal())
    return sum(isinstance(event.payload, RoleRevealed) for event in result.journal)


def test_a_bid_below_the_urgency_threshold_wins_nothing() -> None:
    """Catégorie Débat et parole: zero is today's behaviour, above it is a floor."""
    bids = {WOLF: Bid(urgency=10, intention="Bof.")}

    demanding = DebateOptions(minimum_urgency=50)
    assert elect(bids, floor=(), rules=demanding, rng=create_rng(1)).winner is None
    assert elect(bids, floor=(), rules=DebateOptions(), rng=create_rng(1)).winner == WOLF


def test_waiting_may_be_taken_off_the_table_for_the_debate() -> None:
    """Catégorie Débat et parole: D-048 makes waiting legal, and configurable."""
    impatient = GameRules(debate=DebateOptions(waiting_allowed=False))
    day = GameState.initial(TABLE, rules=impatient).entering(Phase.DAY, day=2)

    with pytest.raises(IllegalIntentError):
        validate_intent(day, WOLF, Wait())

    assert IntentKind.WAIT not in project(day, WOLF).allowed_intents


def test_waiting_stays_legal_where_nothing_else_is_on_offer() -> None:
    """Night 0 has no action at all (D-032): forbidding silence would deadlock it."""
    impatient = GameRules(debate=DebateOptions(waiting_allowed=False))

    validate_intent(GameState.initial(TABLE, rules=impatient), WOLF, Wait())


async def test_a_moderator_who_calls_time_before_the_debate_opens_forces_the_vote() -> None:
    """Catégorie Vote: the moderator's control, set before the game (D-048)."""
    hurried = GameRules(vote=VoteOptions(turns_before_forced_vote=0))
    state = create_game(hurried, rng=create_rng(3))
    agents: dict[PlayerId, Agent] = {
        player.id: RandomAgent(rng=create_rng(3)) for player in state.players
    }

    result = await play_game(state, agents, journal=Journal())
    forced = [event.payload for event in result.journal if isinstance(event.payload, VoteForced)]

    assert forced, "the vote was called rather than debated"
    assert forced[0].reason is ForcedVoteReason.MODERATOR


def test_the_pack_shares_the_budget_of_points_it_was_given() -> None:
    """Catégorie Nuit."""
    generous = GameRules(night=NightOptions(priority_budget=250))
    state = night_of(generous)

    assert project(state, WOLF).priority_budget == 250
    validate_intent(
        state, WOLF, SharePriority(allocations=(PriorityPoint(target=SEER, points=250),))
    )

    with pytest.raises(IllegalIntentError):
        validate_intent(
            night_of(GameRules()),
            WOLF,
            SharePriority(allocations=(PriorityPoint(target=SEER, points=250),)),
        )


async def test_a_day_may_be_given_fewer_turns_at_the_floor() -> None:
    """Catégorie Débat et parole: the ceiling on model calls is a setting (GL-7).

    Not a rule of the game: a debate is meant to end when the last player votes
    (D-013). This only stops a table that never does from spending an unbounded
    number of calls.
    """
    assert await _turns_before_the_budget_ran_out(1) == 8, "one turn each, at a table of eight"
    assert await _turns_before_the_budget_ran_out(2) == 16


async def _turns_before_the_budget_ran_out(turns_per_player: int) -> int:
    """How many turns at the floor a day of endless talkers actually held.

    Counting them is the point: asserting only that the budget *eventually* ran
    out would pass whatever number the engine used, which is a test that cannot
    fail.
    """
    rules = GameRules(debate=DebateOptions(turns_per_player_per_day=turns_per_player))
    state = create_game(rules, rng=create_rng(3))
    agents: dict[PlayerId, Agent] = {player.id: _NeverVotes() for player in state.players}
    journal = Journal()

    # A table that talks and never votes eliminates nobody, so the game runs out
    # of rounds — the round budget doing its job (D-078), not what is under test.
    with pytest.raises(GameDidNotEndError):
        await play_game(state, agents, journal=journal, max_rounds=2)

    spoken = 0
    for event in journal.events:
        match event.payload:
            case SpeechDelivered():
                spoken += 1
            case VoteForced() as forced:
                assert forced.reason is ForcedVoteReason.TURN_BUDGET_SPENT
                return spoken
    raise AssertionError("the day never closed on its budget")


class _NeverVotes(Scripted):
    """A player who always wants the floor and never closes the round."""

    async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
        return Bid(urgency=100, intention="J'ai encore quelque chose à dire.")

    async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
        return Turn(intent=TakeTurn(speech="Je parle.") if view.may_speak else Wait())


def test_the_night_calls_the_roles_in_the_order_it_was_given() -> None:
    """Catégorie Nuit: the seer is free to move, the witch is not (D-029)."""
    seer_last = GameRules(
        night=NightOptions(wake_order=(RoleName.WEREWOLF, RoleName.WITCH, RoleName.SEER))
    )

    assert [player.role for player in night_callers(night_of(seer_last))][:3] == [
        RoleName.WEREWOLF,
        RoleName.WITCH,
        RoleName.SEER,
    ]
    assert [player.role for player in night_callers(night_of(GameRules()))][:3] == [
        RoleName.SEER,
        RoleName.WEREWOLF,
        RoleName.WITCH,
    ]
