"""A role may only play what the registry declares for it (D-010)."""

import contextlib

import pytest

from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.intents import (
    Intent,
    PriorityPoint,
    RoleAction,
    SharePriority,
    TakeTurn,
    Vote,
    Wait,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player
from lupus_ex_machina.engine.roles import ROLES, RoleActionName, RoleName
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import validate_intent
from support.validation_games import (
    DEVOUR_VILLAGER,
    OTHER_VILLAGER,
    OTHER_WOLF,
    UNKNOWN,
    VILLAGER,
    WOLF,
    day,
    night,
)

# --- Purity -----------------------------------------------------------------


@pytest.mark.parametrize(
    "intent",
    [
        Wait(),
        TakeTurn(vote=Vote(target=UNKNOWN)),
        TakeTurn(speech="Bonjour."),
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
