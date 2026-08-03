"""Building the initial state of a game.

Compositions follow D-056: one wolf at six players, two at seven and eight.
The powered roles (seer, witch, hunter) join the composition in J4; here every
non-wolf is a villager.
"""

import pytest

from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.roles import RoleName, Team
from lupus_ex_machina.engine.setup import (
    MAXIMUM_PLAYERS,
    MINIMUM_PLAYERS,
    WEREWOLVES_BY_PLAYER_COUNT,
    UnsupportedPlayerCountError,
    create_game,
)


@pytest.mark.parametrize(("player_count", "wolves"), [(6, 1), (7, 2), (8, 2)])
def test_compositions_follow_the_decided_table(player_count: int, wolves: int) -> None:
    state = create_game(player_count, rng=create_rng(1))

    assert len(state.players) == player_count
    assert len(state.living_of_team(Team.WEREWOLVES)) == wolves
    assert len(state.living_of_team(Team.VILLAGE)) == player_count - wolves


@pytest.mark.parametrize("player_count", [0, 1, MINIMUM_PLAYERS - 1, MAXIMUM_PLAYERS + 1, 20])
def test_unsupported_player_counts_are_refused(player_count: int) -> None:
    """Six to eight players in V1, eight being the hard maximum (D-056)."""
    with pytest.raises(UnsupportedPlayerCountError):
        create_game(player_count, rng=create_rng(1))


def test_the_supported_range_has_no_hole() -> None:
    """The bounds are read off the table, and both refusals word themselves as a range.

    The engine says "V1 supports 6 to 8 players" and the console command says the
    same in French. A count missing from the middle of the table would turn both
    sentences into a lie, and nothing else would notice.
    """
    assert set(WEREWOLVES_BY_PLAYER_COUNT) == set(range(MINIMUM_PLAYERS, MAXIMUM_PLAYERS + 1))


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
