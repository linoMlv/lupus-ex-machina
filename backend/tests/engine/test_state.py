"""Game state: immutability, lookups and phase moves.

Immutability is the property the whole engine rests on: a transition that
mutated its input would make replay (J3) and determinism (J2.6) impossible.
"""

import pytest
from pydantic import ValidationError

from lupus_ex_machina.engine.errors import IllegalTransitionError
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleName, Team
from lupus_ex_machina.engine.state import GameState

WOLF = PlayerId("p0")
VILLAGER = PlayerId("p1")
OTHER_VILLAGER = PlayerId("p2")


def three_player_state() -> GameState:
    return GameState.initial(
        (
            Player(id=WOLF, name="Alice", seat=0, role=RoleName.WEREWOLF),
            Player(id=VILLAGER, name="Bruno", seat=1, role=RoleName.VILLAGER),
            Player(id=OTHER_VILLAGER, name="Camille", seat=2, role=RoleName.VILLAGER),
        )
    )


def test_a_game_starts_at_night_zero_before_the_first_day() -> None:
    state = three_player_state()

    assert state.phase is Phase.NIGHT_ZERO
    assert state.day == 0
    assert len(state.living) == 3


def test_the_state_cannot_be_mutated_in_place() -> None:
    state = three_player_state()

    with pytest.raises(ValidationError):
        state.phase = Phase.DAY


def test_a_player_cannot_be_mutated_in_place() -> None:
    player = three_player_state().player(WOLF)

    with pytest.raises(ValidationError):
        player.alive = False


def test_killing_a_player_leaves_the_source_state_untouched() -> None:
    state = three_player_state()

    bereaved = state.with_players_killed([VILLAGER])

    assert state.is_alive(VILLAGER), "the source state must not be mutated"
    assert not bereaved.is_alive(VILLAGER)
    assert len(bereaved.living) == 2


def test_killing_an_already_dead_player_changes_nothing() -> None:
    state = three_player_state().with_players_killed([VILLAGER])

    assert state.with_players_killed([VILLAGER]) == state


def test_several_players_die_at_once() -> None:
    state = three_player_state().with_players_killed([WOLF, VILLAGER])

    assert [player.id for player in state.living] == [OTHER_VILLAGER]


def test_living_of_team_separates_the_two_sides() -> None:
    state = three_player_state()

    assert len(state.living_of_team(Team.WEREWOLVES)) == 1
    assert len(state.living_of_team(Team.VILLAGE)) == 2


def test_looking_up_an_unknown_player_fails_loudly() -> None:
    state = three_player_state()

    assert not state.has_player(PlayerId("ghost"))
    assert not state.is_alive(PlayerId("ghost"))
    with pytest.raises(KeyError):
        state.player(PlayerId("ghost"))


def test_entering_a_phase_follows_the_transition_table() -> None:
    state = three_player_state()

    day = state.entering(Phase.DAY, day=1)

    assert day.phase is Phase.DAY
    assert day.day == 1
    assert state.phase is Phase.NIGHT_ZERO, "the source state must not be mutated"


def test_entering_an_illegal_phase_is_refused() -> None:
    state = three_player_state()

    with pytest.raises(IllegalTransitionError):
        state.entering(Phase.NIGHT)


def test_entering_a_phase_keeps_the_current_day_by_default() -> None:
    state = three_player_state().entering(Phase.DAY, day=1).entering(Phase.RESOLUTION)

    assert state.day == 1
