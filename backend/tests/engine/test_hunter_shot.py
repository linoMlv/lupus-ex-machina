"""Who owes a shot, and what firing one does (D-030, D-049)."""

import pytest

from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.hunter import hunters_owing_a_shot
from lupus_ex_machina.engine.intents import Wait
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.roles import RoleActionName
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import validate_intent
from support.shots import (
    HUNTER,
    SEER,
    TABLE,
    VILLAGER,
    WOLF,
    dying_hunter,
    shot,
)

# --- Who owes a shot ---------------------------------------------------------


def test_a_dead_hunter_owes_a_shot() -> None:
    assert [player.id for player in hunters_owing_a_shot(dying_hunter())] == [HUNTER]


def test_a_living_hunter_owes_nothing() -> None:
    state = GameState.initial(TABLE).entering(Phase.DAY, day=2)

    assert hunters_owing_a_shot(state) == ()


def test_a_hunter_who_already_fired_owes_nothing() -> None:
    """The trigger fires once, which is also what stops two hunters looping."""
    state = dying_hunter().with_power_spent_by(HUNTER, RoleActionName.SHOOT)

    assert hunters_owing_a_shot(state) == ()


def test_nobody_else_takes_anyone_along() -> None:
    state = (
        GameState.initial(TABLE)
        .entering(Phase.DAY, day=2)
        .entering(Phase.RESOLUTION)
        .with_players_killed([SEER, VILLAGER])
        .entering(Phase.AVENGING_SHOT)
    )

    assert hunters_owing_a_shot(state) == ()


# --- Firing (J4.6.1, J4.6.4) -------------------------------------------------


def test_the_hunter_may_shoot_a_living_player() -> None:
    validate_intent(dying_hunter(), HUNTER, shot(WOLF))


def test_a_dead_hunter_owing_a_shot_is_the_one_dead_player_who_may_act() -> None:
    """Everybody else who died stays out of it, in that phase as in any other.

    Whether he *may* decline is not a matter of legality but of configuration
    (D-055): when the shot is non-renounceable, the engine fires for him.
    """
    validate_intent(dying_hunter(), HUNTER, Wait())

    state = dying_hunter().with_players_killed([SEER])
    with pytest.raises(IllegalIntentError, match="dead"):
        validate_intent(state, SEER, Wait())


def test_the_hunter_may_not_shoot_the_dead() -> None:
    state = dying_hunter().with_players_killed([WOLF])

    with pytest.raises(IllegalIntentError, match="dead"):
        validate_intent(state, HUNTER, shot(WOLF))


def test_the_hunter_may_not_shoot_himself() -> None:
    with pytest.raises(IllegalIntentError, match="themselves"):
        validate_intent(dying_hunter(), HUNTER, shot(HUNTER))


def test_nobody_but_a_hunter_may_fire() -> None:
    with pytest.raises(IllegalIntentError, match="cannot shoot"):
        validate_intent(dying_hunter(), WOLF, shot(SEER))


def test_the_shot_belongs_to_its_own_phase() -> None:
    """Fired by day and in public (D-030), never in the middle of the night."""
    night = (
        GameState.initial(TABLE)
        .entering(Phase.DAY, day=1)
        .entering(Phase.RESOLUTION)
        .entering(Phase.NIGHT)
    )

    with pytest.raises(IllegalIntentError):
        validate_intent(night, HUNTER, shot(WOLF))


def test_a_hunter_fires_once() -> None:
    """Having fired, he is a dead player like any other."""
    state = dying_hunter().with_power_spent_by(HUNTER, RoleActionName.SHOOT)

    with pytest.raises(IllegalIntentError, match="dead"):
        validate_intent(state, HUNTER, shot(WOLF))


def test_a_living_hunter_has_nothing_to_fire() -> None:
    """The shot answers a death; there is no phase for it while he is alive."""
    alive = GameState.initial(TABLE).entering(Phase.DAY, day=2)

    with pytest.raises(IllegalIntentError, match="not played during"):
        validate_intent(alive, HUNTER, shot(WOLF))
