"""Dealing a game.

The table itself is decided elsewhere (see the composition tests); what is
checked here is the deal: every role of the composition reaches exactly one
seat, names are drawn without replacement, and the whole thing comes from the
seed and nothing else.
"""

from collections import Counter

import pytest

from lupus_ex_machina.engine.composition import (
    MAXIMUM_PLAYERS,
    MINIMUM_PLAYERS,
    Composition,
    UnsupportedPlayerCountError,
    default_composition,
)
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.setup import create_game

TABLE_SIZES = range(MINIMUM_PLAYERS, MAXIMUM_PLAYERS + 1)


@pytest.mark.parametrize("player_count", TABLE_SIZES)
def test_a_deal_hands_out_exactly_the_composition(player_count: int) -> None:
    state = create_game(player_count, rng=create_rng(1))

    assert Counter(player.role for player in state.players) == Counter(
        default_composition(player_count).roles
    )


@pytest.mark.parametrize("player_count", TABLE_SIZES)
def test_every_supported_table_deals_all_five_roles(player_count: int) -> None:
    """The powered roles are not an option of the default game (D-056)."""
    dealt = {player.role for player in create_game(player_count, rng=create_rng(1)).players}

    assert dealt == set(RoleName)


def test_a_game_can_be_dealt_from_a_composition_of_ones_own() -> None:
    """D-061: the owner may deal their own table, and it is dealt as given."""
    composition = Composition(
        roles=(RoleName.WEREWOLF, RoleName.WEREWOLF, RoleName.HUNTER) + (RoleName.VILLAGER,) * 3
    )

    state = create_game(composition, rng=create_rng(1))

    assert Counter(player.role for player in state.players) == Counter(composition.roles)
    assert len(state.players) == 6


@pytest.mark.parametrize("player_count", [0, 1, MINIMUM_PLAYERS - 1, MAXIMUM_PLAYERS + 1, 20])
def test_unsupported_player_counts_are_refused(player_count: int) -> None:
    with pytest.raises(UnsupportedPlayerCountError):
        create_game(player_count, rng=create_rng(1))


def test_players_are_seated_in_order_and_all_alive() -> None:
    state = create_game(8, rng=create_rng(7))

    assert [player.seat for player in state.players] == list(range(8))
    assert all(player.alive for player in state.players)


def test_players_get_distinct_identities_and_names() -> None:
    state = create_game(8, rng=create_rng(7))

    assert len({player.id for player in state.players}) == 8
    assert len({player.name for player in state.players}) == 8


def test_the_same_seed_deals_the_same_game() -> None:
    first = create_game(8, rng=create_rng(42))
    second = create_game(8, rng=create_rng(42))

    assert first == second


def test_different_seeds_deal_different_games() -> None:
    """Not a strict guarantee, but two seeds must not be locked to one deal."""
    deals = {
        tuple(player.role for player in create_game(8, rng=create_rng(seed)).players)
        for seed in range(20)
    }

    assert len(deals) > 1


def test_roles_are_not_always_dealt_to_the_same_seats() -> None:
    wolf_seats = {
        next(
            player.seat
            for player in create_game(8, rng=create_rng(seed)).players
            if player.role is RoleName.WEREWOLF
        )
        for seed in range(20)
    }

    assert len(wolf_seats) > 1
