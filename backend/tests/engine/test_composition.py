"""Who sits at the table.

The three default compositions are the ones the project owner wrote out (D-056),
so they are pinned value by value rather than derived from a ratio: a ratio would
drift from them silently the day the table grows.

A custom composition is allowed (D-061) and checked against one thing — that the
game it describes has not already been won before anybody speaks. That check is
delegated to the victory rule itself, so the two cannot drift apart.
"""

import pytest
from pydantic import ValidationError

from lupus_ex_machina.engine.composition import (
    DEFAULT_COMPOSITIONS,
    MAXIMUM_PLAYERS,
    MINIMUM_PLAYERS,
    Composition,
    UnsupportedPlayerCountError,
    default_composition,
)
from lupus_ex_machina.engine.roles import RoleName, Team, team_of

#: D-056, written out. Six players: one wolf. Seven and eight: two.
DECIDED = {
    6: {
        RoleName.WEREWOLF: 1,
        RoleName.SEER: 1,
        RoleName.WITCH: 1,
        RoleName.HUNTER: 1,
        RoleName.VILLAGER: 2,
    },
    7: {
        RoleName.WEREWOLF: 2,
        RoleName.SEER: 1,
        RoleName.WITCH: 1,
        RoleName.HUNTER: 1,
        RoleName.VILLAGER: 2,
    },
    8: {
        RoleName.WEREWOLF: 2,
        RoleName.SEER: 1,
        RoleName.WITCH: 1,
        RoleName.HUNTER: 1,
        RoleName.VILLAGER: 3,
    },
}


def a_table(werewolves: int, villagers: int) -> tuple[RoleName, ...]:
    return (RoleName.WEREWOLF,) * werewolves + (RoleName.VILLAGER,) * villagers


# --- The decided table -------------------------------------------------------


@pytest.mark.parametrize("player_count", sorted(DECIDED))
def test_the_default_compositions_are_the_ones_that_were_decided(player_count: int) -> None:
    composition = default_composition(player_count)

    assert {role: composition.count(role) for role in RoleName} == DECIDED[player_count]


@pytest.mark.parametrize("player_count", sorted(DECIDED))
def test_a_composition_seats_exactly_the_table_it_is_asked_for(player_count: int) -> None:
    assert default_composition(player_count).size == player_count


def test_every_supported_table_size_has_a_composition() -> None:
    assert set(DEFAULT_COMPOSITIONS) == set(range(MINIMUM_PLAYERS, MAXIMUM_PLAYERS + 1))


@pytest.mark.parametrize("player_count", [0, 1, MINIMUM_PLAYERS - 1, MAXIMUM_PLAYERS + 1, 20])
def test_unsupported_table_sizes_are_refused(player_count: int) -> None:
    """Six to eight players in V1, eight being the hard maximum (D-056)."""
    with pytest.raises(UnsupportedPlayerCountError, match="players"):
        default_composition(player_count)


def test_every_default_composition_has_exactly_one_of_each_powered_role() -> None:
    """A second seer or witch is legal, but it is not what the defaults deal."""
    for composition in DEFAULT_COMPOSITIONS.values():
        for role in (RoleName.SEER, RoleName.WITCH, RoleName.HUNTER):
            assert composition.count(role) == 1


# --- A composition describes a game that can still be played -----------------


def test_a_custom_composition_is_accepted_when_it_holds_together() -> None:
    """D-061: the owner may deal their own table."""
    composition = Composition(roles=a_table(werewolves=2, villagers=4))

    assert composition.size == 6
    assert composition.count(RoleName.WEREWOLF) == 2


def test_a_table_without_a_single_wolf_is_refused() -> None:
    """The village would have won before the first night."""
    with pytest.raises(ValidationError, match="already over"):
        Composition(roles=a_table(werewolves=0, villagers=6))


def test_a_table_of_nothing_but_wolves_is_refused() -> None:
    with pytest.raises(ValidationError, match="already over"):
        Composition(roles=a_table(werewolves=6, villagers=0))


def test_a_table_the_wolves_have_already_won_is_refused() -> None:
    with pytest.raises(ValidationError, match="already over"):
        Composition(roles=a_table(werewolves=4, villagers=2))


def test_wolves_matching_villagers_is_a_playable_table() -> None:
    """At parity the game continues, unless only two players remain (D-059)."""
    assert Composition(roles=a_table(werewolves=3, villagers=3)).size == 6


@pytest.mark.parametrize("size", [0, 1, MINIMUM_PLAYERS - 1, MAXIMUM_PLAYERS + 1])
def test_a_table_outside_the_supported_range_is_refused(size: int) -> None:
    with pytest.raises(ValidationError, match="players"):
        Composition(roles=a_table(werewolves=1, villagers=max(size - 1, 0)))


def test_a_composition_is_frozen() -> None:
    composition = default_composition(8)

    with pytest.raises(ValidationError):
        composition.roles = ()


# --- The rule that accepts a table is the rule that ends a game ---------------


def test_no_accepted_composition_describes_a_game_already_won() -> None:
    """Guard against the two rules drifting apart.

    The composition check and the end condition answer the same question, so
    they read it from the same place. If they ever stopped agreeing, a table
    would be dealt that the very first evaluation would declare finished.
    """
    for composition in DEFAULT_COMPOSITIONS.values():
        wolves = sum(1 for role in composition.roles if team_of(role) is Team.WEREWOLVES)
        villagers = composition.size - wolves

        assert wolves > 0
        assert villagers > wolves or (villagers == wolves and composition.size > 2)
