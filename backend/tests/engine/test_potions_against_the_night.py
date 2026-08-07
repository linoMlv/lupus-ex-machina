"""What the witch's two potions do to a night (D-029)."""

from lupus_ex_machina.engine.intents import (
    PriorityPoint,
)
from lupus_ex_machina.engine.night import resolve_night
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import RoleActionName
from lupus_ex_machina.engine.state import GameState
from support.scenarios import A_TABLE_WITH_A_WITCH, OTHER_PREY, PACK, PREY, WITCH

# --- Potions against the night (J4.7.1) --------------------------------------


def a_night_where_the_pack_took(target: PlayerId) -> GameState:
    return (
        GameState.initial(A_TABLE_WITH_A_WITCH)
        .entering(Phase.DAY, day=1)
        .entering(Phase.RESOLUTION)
        .entering(Phase.NIGHT)
        .with_priority_share_from(PACK, (PriorityPoint(target=target, points=100),))
    )


def test_the_potion_of_life_answers_the_bite() -> None:
    state = a_night_where_the_pack_took(PREY).with_night_choice_from(
        WITCH, RoleActionName.HEAL, PREY
    )

    resolved, victims = resolve_night(state)

    assert victims == ()
    assert len(resolved.living) == len(A_TABLE_WITH_A_WITCH)


def test_the_witch_taken_by_the_pack_can_save_herself() -> None:
    """The only night she survives, and the reason the potion may target her (D-029)."""
    state = a_night_where_the_pack_took(WITCH).with_night_choice_from(
        WITCH, RoleActionName.HEAL, WITCH
    )

    resolved, victims = resolve_night(state)

    assert victims == ()
    assert resolved.is_alive(WITCH)


def test_poisoning_the_player_the_pack_already_took_kills_them_once() -> None:
    """Two claims on one player, one death — the run of victims holds no duplicate."""
    state = a_night_where_the_pack_took(PREY).with_night_choice_from(
        WITCH, RoleActionName.POISON, PREY
    )

    resolved, victims = resolve_night(state)

    assert victims == (PREY,)
    assert len(resolved.living) == len(A_TABLE_WITH_A_WITCH) - 1


def test_a_night_can_take_the_pack_s_prey_and_the_poisoned_one() -> None:
    state = a_night_where_the_pack_took(PREY).with_night_choice_from(
        WITCH, RoleActionName.POISON, OTHER_PREY
    )

    _, victims = resolve_night(state)

    assert set(victims) == {PREY, OTHER_PREY}
