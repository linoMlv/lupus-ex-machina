"""Playing a whole game, start to finish.

These are the safety nets of the project: they catch deadlocks, unreachable
states and terminations that regress, for almost no runtime cost.
"""

import itertools

import pytest

from lupus_ex_machina.agents.scripted import (
    AlwaysAccuseAgent,
    SilentAgent,
)
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.runner import (
    GameDidNotEndError,
    GameResult,
    play_game,
)
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.victory import Outcome, evaluate_victory
from support.games import (
    FORCED,
    PLAYER_COUNTS,
    assert_properly_finished,
    play,
)

# --- A game runs to the end -------------------------------------------------


async def test_a_full_game_reaches_a_winner() -> None:
    assert_properly_finished(await play(seed=1))


@pytest.mark.parametrize("player_count", PLAYER_COUNTS)
async def test_every_supported_table_size_can_be_played(player_count: int) -> None:
    assert_properly_finished(await play(seed=2, player_count=player_count))


async def test_a_hundred_games_of_different_seeds_all_terminate() -> None:
    """The regression net of J2.5.5: no seed may deadlock the engine."""
    results = [await play(seed=seed) for seed in range(100)]

    for result in results:
        assert_properly_finished(result)
    assert len({result.outcome for result in results}) == 2, "both sides must be able to win"


async def test_a_table_that_always_accuses_ends_quickly() -> None:
    """Eight players, an elimination most rounds: the game cannot drag on.

    The bound is what makes the name true — without it the round budget of 100
    would let a stalling regression through unnoticed.
    """
    state = create_game(rng=create_rng(4))
    agents: dict[PlayerId, Agent] = {player.id: AlwaysAccuseAgent() for player in state.players}

    result = await play_game(state, agents)

    assert_properly_finished(result)
    assert result.rounds <= 8


async def test_a_table_where_nobody_ever_dies_is_stopped_by_the_round_budget() -> None:
    """A degenerate table, and a real property of the rules.

    If every player votes blank and the pack designates nobody, no rule kills
    anyone, so the game genuinely never ends: a tie spares everyone (D-050) and
    the forced vote only closes the round, it does not eliminate. The round
    budget exists to turn that into a loud failure rather than a hang.
    """
    state = create_game(rng=create_rng(4))
    agents: dict[PlayerId, Agent] = {player.id: SilentAgent() for player in state.players}

    with pytest.raises(GameDidNotEndError):
        await play_game(state, agents, max_rounds=10)


async def test_the_same_table_ends_when_the_pack_is_made_to_designate_someone() -> None:
    """The way out of that deadlock the configuration offers (D-078, D-081).

    Same silent table, same seed: made to take someone every night, the pack
    eats the village and wins. Nothing else about the game changed.
    """
    rng = create_rng(4)
    state = create_game(FORCED, rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: SilentAgent() for player in state.players}

    result = await play_game(state, agents, max_rounds=10, rng=rng)

    assert_properly_finished(result)
    assert result.outcome is Outcome.WEREWOLVES_WIN


async def test_the_prey_the_lot_takes_depends_on_the_seed() -> None:
    """What D-081 bought: the same deadlock no longer kills the same players.

    A pack settled by seat took the lowest one every time, in every game.
    """
    victims = {await _who_the_lot_took(seed) for seed in range(12)}

    assert len(victims) > 1


async def _who_the_lot_took(seed: int) -> tuple[PlayerId, ...]:
    """Play the deadlocked table with one seed and report who the pack ate."""
    rng = create_rng(seed)
    state = create_game(FORCED, rng=create_rng(4))
    agents: dict[PlayerId, Agent] = {player.id: SilentAgent() for player in state.players}

    result = await play_game(state, agents, max_rounds=10, rng=rng)
    return tuple(player.id for player in result.state.players if not player.alive)


# --- Determinism ------------------------------------------------------------


def game_of(result: GameResult) -> tuple[object, ...]:
    """Everything a seed is supposed to reproduce.

    The journal is compared fact by fact, envelope included, minus the one field
    a seed cannot govern: the timestamps come from the wall clock, and belong to
    the recording rather than to the game.
    """
    return (
        result.state,
        result.outcome,
        result.rounds,
        result.rejected_intents,
        tuple((event.sequence, event.phase, event.day, event.payload) for event in result.journal),
    )


async def test_two_games_with_the_same_seed_are_identical() -> None:
    first, second = await play(seed=7), await play(seed=7)

    assert game_of(first) == game_of(second)


async def test_different_seeds_produce_different_games() -> None:
    lengths = {(await play(seed=seed)).rounds for seed in range(20)}

    assert len(lengths) > 1


# --- Victory is evaluated once the resolution is complete -------------------


async def test_the_game_stops_as_soon_as_a_side_has_won() -> None:
    result = await play(seed=3)

    assert evaluate_victory(result.state) is result.outcome


async def test_a_finished_game_always_leaves_a_survivor() -> None:
    for seed in range(100):
        result = await play(seed=seed)

        assert result.state.living, f"seed {seed} wiped out the whole table"


@pytest.mark.parametrize(
    ("wolves", "villagers"),
    [(w, v) for w, v in itertools.product(range(9), repeat=2) if 0 < w + v <= 2],
)
def test_no_game_with_two_survivors_or_fewer_is_still_running(wolves: int, villagers: int) -> None:
    """Why "everybody dies" is unreachable: such a game is already over (D-059).

    A night can only start from a running game, and no running game has two
    players or fewer, so no night can take the table from two to zero.
    """
    players = tuple(
        Player(
            id=PlayerId(f"p{seat}"),
            name=f"J{seat}",
            seat=seat,
            role=RoleName.WEREWOLF if seat < wolves else RoleName.VILLAGER,
        )
        for seat in range(wolves + villagers)
    )

    assert evaluate_victory(GameState.initial(players)) is not None
