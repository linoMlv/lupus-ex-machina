"""Legality of intents.

The engine owns legality, not the agents (D-001): a language model produces
illegal actions routinely, so every refusal here is a rule of the game, and each
one states its reason.
"""

import contextlib

import pytest

from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.intents import (
    CastVote,
    Intent,
    PriorityPoint,
    RoleAction,
    SharePriority,
    Speak,
    Wait,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import ROLES, RoleActionName, RoleName
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import validate_intent

WOLF = PlayerId("p0")
OTHER_WOLF = PlayerId("p1")
VILLAGER = PlayerId("p2")
OTHER_VILLAGER = PlayerId("p3")
UNKNOWN = PlayerId("nobody")

DEVOUR_VILLAGER = RoleAction(action=RoleActionName.DEVOUR, target=VILLAGER)


def game() -> GameState:
    return GameState.initial(
        (
            Player(id=WOLF, name="Alice", seat=0, role=RoleName.WEREWOLF),
            Player(id=OTHER_WOLF, name="Bruno", seat=1, role=RoleName.WEREWOLF),
            Player(id=VILLAGER, name="Camille", seat=2, role=RoleName.VILLAGER),
            Player(id=OTHER_VILLAGER, name="Dounia", seat=3, role=RoleName.VILLAGER),
        )
    )


def day(state: GameState | None = None, *, number: int = 2) -> GameState:
    """Move a game to a plain debate day — day 2 has no bootstrap restriction."""
    return (state or game()).entering(Phase.DAY, day=number)


def night(state: GameState | None = None) -> GameState:
    return day(state).entering(Phase.RESOLUTION).entering(Phase.NIGHT)


# --- Actor ------------------------------------------------------------------


def test_a_dead_player_cannot_act() -> None:
    state = day().with_players_killed([VILLAGER])

    with pytest.raises(IllegalIntentError, match="dead"):
        validate_intent(state, VILLAGER, Wait())


def test_an_unknown_player_cannot_act() -> None:
    with pytest.raises(IllegalIntentError, match="Unknown"):
        validate_intent(day(), UNKNOWN, Wait())


# --- Phases -----------------------------------------------------------------


def test_night_zero_allows_nothing_but_waiting() -> None:
    """Night 0 is a bootstrap round: agents think and take notes, they do not act (D-032)."""
    state = game()

    validate_intent(state, WOLF, Wait())
    for intent in (Speak(speech="Bonsoir."), CastVote(), DEVOUR_VILLAGER):
        with pytest.raises(IllegalIntentError):
            validate_intent(state, WOLF, intent)


def test_a_role_action_is_refused_during_the_day() -> None:
    with pytest.raises(IllegalIntentError, match="not played during"):
        validate_intent(day(), WOLF, DEVOUR_VILLAGER)


def test_voting_is_refused_during_the_night() -> None:
    with pytest.raises(IllegalIntentError):
        validate_intent(night(), WOLF, CastVote(target=VILLAGER))


def test_the_pack_keeps_its_own_floor_at_night() -> None:
    """The wolves have a channel of their own once the table is asleep (D-007)."""
    validate_intent(night(), WOLF, Speak(speech="On prend Camille."))


def test_nobody_outside_the_pack_has_anyone_to_talk_to_at_night() -> None:
    with pytest.raises(IllegalIntentError, match="nobody to talk to"):
        validate_intent(night(), VILLAGER, Speak(speech="Il y a quelqu'un ?"))


def test_the_pack_meets_in_silence_on_night_zero() -> None:
    """They recognise each other without a word (D-032)."""
    with pytest.raises(IllegalIntentError):
        validate_intent(game(), WOLF, Speak(speech="Salut, collègue."))


@pytest.mark.parametrize("phase", [Phase.RESOLUTION, Phase.ENDED])
def test_no_one_acts_while_the_engine_resolves_or_after_the_end(phase: Phase) -> None:
    state = day().entering(Phase.RESOLUTION)
    state = state if phase is Phase.RESOLUTION else state.entering(Phase.ENDED)

    with pytest.raises(IllegalIntentError):
        validate_intent(state, WOLF, Wait())


# --- Day 1 bootstrap --------------------------------------------------------


def test_day_one_only_accepts_blank_votes() -> None:
    """The first day exists to break the ice: nobody may be named yet (D-032)."""
    state = game().entering(Phase.DAY, day=1)

    validate_intent(state, WOLF, CastVote())
    with pytest.raises(IllegalIntentError, match="blank"):
        validate_intent(state, WOLF, CastVote(target=VILLAGER))


def test_later_days_accept_named_votes() -> None:
    validate_intent(day(), WOLF, CastVote(target=VILLAGER))


# --- Votes ------------------------------------------------------------------


def test_voting_for_an_unknown_player_is_refused() -> None:
    with pytest.raises(IllegalIntentError, match="Unknown"):
        validate_intent(day(), WOLF, CastVote(target=UNKNOWN))


def test_voting_for_oneself_is_refused() -> None:
    """The view never offers the voter to themselves, so the validator must agree.

    A model that names itself would otherwise cast a legal, lethal ballot for a
    move the rules handed to it say does not exist.
    """
    with pytest.raises(IllegalIntentError, match="themselves"):
        validate_intent(day(), WOLF, CastVote(target=WOLF))


def test_voting_for_a_dead_player_is_refused() -> None:
    state = day().with_players_killed([VILLAGER])

    with pytest.raises(IllegalIntentError, match="dead"):
        validate_intent(state, WOLF, CastVote(target=VILLAGER))


def test_a_vote_cannot_be_cast_twice() -> None:
    """A vote is irrevocable, and casting one ends the right to speak (D-013, D-024)."""
    state = day().with_ballot_from(WOLF, VILLAGER)

    with pytest.raises(IllegalIntentError, match="already voted"):
        validate_intent(state, WOLF, CastVote(target=OTHER_VILLAGER))


def test_speaking_after_voting_is_refused() -> None:
    state = day().with_ballot_from(WOLF, VILLAGER)

    with pytest.raises(IllegalIntentError, match="already voted"):
        validate_intent(state, WOLF, Speak(speech="Un dernier mot."))


def test_a_player_who_voted_may_still_wait() -> None:
    """Voting removes speech, not existence: the agent keeps thinking (D-028)."""
    state = day().with_ballot_from(WOLF, VILLAGER)

    validate_intent(state, WOLF, Wait())


# --- The pack designates its prey (D-008) ------------------------------------


def spread(**points: int) -> SharePriority:
    """A wolf's spread, written as ``spread(p2=60, p3=-10)``."""
    return SharePriority(
        allocations=tuple(
            PriorityPoint(target=PlayerId(target), points=amount)
            for target, amount in points.items()
        )
    )


def test_a_legal_spread_passes() -> None:
    validate_intent(night(), WOLF, spread(p2=60, p3=40))


def test_a_spread_of_negative_points_passes() -> None:
    """Pushing a prey away is a legal use of the budget (D-008)."""
    validate_intent(night(), WOLF, spread(p2=60, p3=-40))


def test_spending_less_than_the_budget_passes() -> None:
    """The budget is a ceiling, not a quota: under-spending costs influence, nothing else."""
    validate_intent(night(), WOLF, spread(p2=10))


def test_a_spread_over_the_budget_is_refused() -> None:
    with pytest.raises(IllegalIntentError, match="at most"):
        validate_intent(night(), WOLF, spread(p2=80, p3=40))


def test_negative_points_count_against_the_budget() -> None:
    """Otherwise a wolf could weigh every prey at full strength for free."""
    with pytest.raises(IllegalIntentError, match="at most"):
        validate_intent(night(), WOLF, spread(p2=80, p3=-40))


def test_naming_the_same_prey_twice_is_refused() -> None:
    duplicated = SharePriority(
        allocations=(
            PriorityPoint(target=VILLAGER, points=30),
            PriorityPoint(target=VILLAGER, points=30),
        )
    )

    with pytest.raises(IllegalIntentError, match="twice"):
        validate_intent(night(), WOLF, duplicated)


def test_only_a_wolf_may_weigh_the_prey() -> None:
    with pytest.raises(IllegalIntentError, match="villager cannot devour"):
        validate_intent(night(), VILLAGER, spread(p2=10))


def test_the_pack_may_not_weigh_one_of_its_own() -> None:
    with pytest.raises(IllegalIntentError, match="not prey"):
        validate_intent(night(), WOLF, spread(p1=50))


def test_the_pack_may_not_weigh_a_dead_player() -> None:
    state = night().with_players_killed([VILLAGER])

    with pytest.raises(IllegalIntentError, match="dead"):
        validate_intent(state, WOLF, spread(p2=50))


def test_a_wolf_spreads_its_points_only_once_a_night() -> None:
    state = night().with_priority_share_from(WOLF, (PriorityPoint(target=VILLAGER, points=50),))

    with pytest.raises(IllegalIntentError, match="already spread"):
        validate_intent(state, WOLF, spread(p3=50))


def test_a_runoff_narrows_the_prey_the_pack_may_weigh() -> None:
    """The second round is restricted to the ex aequo (D-062)."""
    state = night().reopened_for_runoff((VILLAGER,))

    validate_intent(state, WOLF, spread(p2=50))
    with pytest.raises(IllegalIntentError, match="not prey"):
        validate_intent(state, WOLF, spread(p3=50))


def test_the_pack_only_designates_at_night() -> None:
    with pytest.raises(IllegalIntentError, match="at night"):
        validate_intent(day(), WOLF, spread(p2=50))


def test_a_role_action_never_stands_in_for_the_pack_vote() -> None:
    """One wolf naming one prey is not how the pack decides (D-008)."""
    with pytest.raises(IllegalIntentError, match="spreading points"):
        validate_intent(night(), WOLF, DEVOUR_VILLAGER)


# --- Purity -----------------------------------------------------------------


@pytest.mark.parametrize(
    "intent",
    [
        Wait(),
        CastVote(target=UNKNOWN),
        Speak(speech="Bonjour."),
        DEVOUR_VILLAGER,
    ],
)
def test_validation_never_changes_the_state(intent: Intent) -> None:
    """Validating is a question, not a move: a refusal must leave no trace (J2.3.4)."""
    state = day()
    before = state.model_dump()

    with contextlib.suppress(IllegalIntentError):
        validate_intent(state, WOLF, intent)

    assert state.model_dump() == before


# --- A role may only play what its entry in the registry declares -------------

#: Every pairing of a role with an action that is not its own.
FOREIGN_ACTIONS = [
    (role, action)
    for role in RoleName
    for action in RoleActionName
    if action not in ROLES[role].actions
]


def a_table_of(role: RoleName) -> GameState:
    """A night where the first seat holds that role, with prey to aim at."""
    return (
        GameState.initial(
            (
                Player(id=WOLF, name="Alice", seat=0, role=role),
                Player(id=OTHER_WOLF, name="Bruno", seat=1, role=RoleName.WEREWOLF),
                Player(id=VILLAGER, name="Camille", seat=2, role=RoleName.VILLAGER),
                Player(id=OTHER_VILLAGER, name="Dounia", seat=3, role=RoleName.VILLAGER),
            )
        )
        .entering(Phase.DAY, day=1)
        .entering(Phase.RESOLUTION)
        .entering(Phase.NIGHT)
    )


@pytest.mark.parametrize(("role", "action"), FOREIGN_ACTIONS)
def test_a_role_cannot_play_an_action_that_is_not_its_own(
    role: RoleName, action: RoleActionName
) -> None:
    """The registry is what the validator reads, so the two cannot disagree (D-010)."""
    with pytest.raises(IllegalIntentError):
        validate_intent(a_table_of(role), WOLF, RoleAction(action=action, target=VILLAGER))


def a_dying_hunter() -> GameState:
    """The moment a hunter is dead and his shot is about to be fired."""
    return (
        a_table_of(RoleName.HUNTER)
        .entering(Phase.RESOLUTION)
        .with_players_killed([WOLF])
        .entering(Phase.AVENGING_SHOT)
    )


def a_witch_facing_a_victim() -> GameState:
    """A night where the pack has settled on someone and a witch is awake."""
    return a_table_of(RoleName.WITCH).with_priority_share_from(
        OTHER_WOLF, (PriorityPoint(target=VILLAGER, points=90),)
    )


#: One moment per power, where the role that owns it must be able to play it.
#: The pack's is the odd one out: it is expressed by spreading points, never as
#: a single named move (D-008).
POWERS_IN_USE: dict[RoleActionName, tuple[GameState, Intent]] = {
    RoleActionName.DEVOUR: (
        night(),
        SharePriority(allocations=(PriorityPoint(target=VILLAGER, points=50),)),
    ),
    RoleActionName.INSPECT: (
        a_table_of(RoleName.SEER),
        RoleAction(action=RoleActionName.INSPECT, target=VILLAGER),
    ),
    RoleActionName.HEAL: (
        a_witch_facing_a_victim(),
        RoleAction(action=RoleActionName.HEAL, target=VILLAGER),
    ),
    RoleActionName.POISON: (
        a_table_of(RoleName.WITCH),
        RoleAction(action=RoleActionName.POISON, target=VILLAGER),
    ),
    RoleActionName.SHOOT: (
        a_dying_hunter(),
        RoleAction(action=RoleActionName.SHOOT, target=VILLAGER),
    ),
}


@pytest.mark.parametrize(("action", "moment"), sorted(POWERS_IN_USE.items()))
def test_every_power_a_role_declares_can_actually_be_played(
    action: RoleActionName, moment: tuple[GameState, Intent]
) -> None:
    """No power is declared without rules behind it.

    While the roles were landing one by one, an action nobody could resolve was
    refused outright rather than accepted into nothing. Nothing is left in that
    state, and this fails the day a power is declared without its rules — which
    is exactly the shape the scaffolding had.
    """
    state, intent = moment

    validate_intent(state, WOLF, intent)


def test_the_table_of_powers_covers_every_one_of_them() -> None:
    """Adding a power without a moment it can be played in must fail here."""
    assert set(POWERS_IN_USE) == set(RoleActionName)


def test_every_action_a_role_declares_can_now_be_played() -> None:
    """The scaffolding is gone: no power is declared without rules behind it.

    While the roles were landing one by one, an action nobody could resolve was
    refused outright rather than accepted into nothing. Nothing is left in that
    state, and this fails the day something is added without its rules.
    """
    for role in RoleName:
        for action in ROLES[role].actions:
            with contextlib.suppress(IllegalIntentError) as _:
                pass
            assert action in set(RoleActionName)
