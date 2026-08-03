"""Playing a whole game.

These are the safety nets of the project: they catch deadlocks, unreachable
states and terminations that regress, for almost no runtime cost.
"""

import itertools

import pytest

from lupus_ex_machina.agents.scripted import AlwaysAccuseAgent, RandomAgent, SilentAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.intents import CastVote, Intent, RoleAction, RoleActionName, Wait
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.runner import GameDidNotEndError, GameResult, play_game
from lupus_ex_machina.engine.setup import MAXIMUM_PLAYERS, MINIMUM_PLAYERS, create_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.victory import Outcome, evaluate_victory
from lupus_ex_machina.engine.views import PlayerView

PLAYER_COUNTS = range(MINIMUM_PLAYERS, MAXIMUM_PLAYERS + 1)


def play(seed: int, *, player_count: int = 8) -> GameResult:
    """Play one full game of random agents, everything derived from one seed."""
    rng = create_rng(seed)
    state = create_game(player_count, rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: RandomAgent(rng=rng) for player in state.players}
    return play_game(state, agents)


# --- A game runs to the end -------------------------------------------------


def test_a_full_game_reaches_a_winner() -> None:
    result = play(seed=1)

    assert result.outcome in tuple(Outcome)
    assert result.state.phase is Phase.ENDED
    assert result.rounds >= 1


@pytest.mark.parametrize("player_count", PLAYER_COUNTS)
def test_every_supported_table_size_can_be_played(player_count: int) -> None:
    assert play(seed=2, player_count=player_count).outcome in tuple(Outcome)


def test_a_hundred_games_of_different_seeds_all_terminate() -> None:
    """The regression net of J2.5.5: no seed may deadlock the engine."""
    outcomes = [play(seed=seed).outcome for seed in range(100)]

    assert len(outcomes) == 100
    assert all(outcome in tuple(Outcome) for outcome in outcomes)
    assert len(set(outcomes)) == 2, "both sides must be able to win"


def test_a_table_that_always_accuses_ends_quickly() -> None:
    state = create_game(8, rng=create_rng(4))
    agents: dict[PlayerId, Agent] = {player.id: AlwaysAccuseAgent() for player in state.players}

    result = play_game(state, agents)

    assert result.outcome in tuple(Outcome)


def test_a_table_where_nobody_ever_dies_is_stopped_by_the_round_budget() -> None:
    """A degenerate table, and a real property of the rules.

    If every player votes blank and the pack designates nobody, no rule kills
    anyone, so the game genuinely never ends: a tie spares everyone (D-050) and
    the forced vote only closes the round, it does not eliminate. The round
    budget exists to turn that into a loud failure rather than a hang.
    """
    state = create_game(8, rng=create_rng(4))
    agents: dict[PlayerId, Agent] = {player.id: SilentAgent() for player in state.players}

    with pytest.raises(GameDidNotEndError):
        play_game(state, agents, max_rounds=10)


# --- Determinism ------------------------------------------------------------


def test_two_games_with_the_same_seed_are_identical() -> None:
    first, second = play(seed=7), play(seed=7)

    assert first == second


def test_different_seeds_produce_different_games() -> None:
    lengths = {play(seed=seed).rounds for seed in range(20)}

    assert len(lengths) > 1


# --- Victory is evaluated once the resolution is complete -------------------


def test_the_game_stops_as_soon_as_a_side_has_won() -> None:
    result = play(seed=3)

    assert evaluate_victory(result.state) is result.outcome


def test_a_finished_game_always_leaves_a_survivor() -> None:
    for seed in range(100):
        result = play(seed=seed)

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


# --- Illegal intents --------------------------------------------------------


class RogueAgent:
    """An agent that answers with an intent the rules refuse, as models do."""

    def decide(self, view: PlayerView) -> Intent:
        """Always try to devour someone, whatever the phase allows."""
        prey = view.living_others[0] if view.living_others else view.self_id
        return RoleAction(action=RoleActionName.DEVOUR, target=prey)


def test_an_agent_playing_illegal_intents_cannot_break_a_game() -> None:
    """The engine owns legality: a refused intent costs a turn, nothing else (D-001).

    One deranged player among sane ones — which is exactly what a misbehaving
    model will look like in J7.
    """
    rng = create_rng(9)
    state = create_game(8, rng=rng)
    agents: dict[PlayerId, Agent] = {
        player.id: RogueAgent() if player.seat == 0 else RandomAgent(rng=rng)
        for player in state.players
    }

    result = play_game(state, agents)

    assert result.outcome in tuple(Outcome)
    assert result.rejected_intents > 0


class NeverVotesAgent:
    """Waits forever: legal (D-048), and a way to stall a round."""

    def decide(self, view: PlayerView) -> Intent:
        """Never do anything."""
        return Wait()


def test_a_player_who_never_votes_does_not_stall_the_round() -> None:
    """Waiting forever is legal, so the round needs its own way out (D-048, D-060)."""
    state = create_game(8, rng=create_rng(10))
    agents: dict[PlayerId, Agent] = {
        player.id: NeverVotesAgent() if player.seat == 0 else AlwaysAccuseAgent()
        for player in state.players
    }

    result = play_game(state, agents)

    assert result.outcome in tuple(Outcome)


def test_the_engine_refuses_to_loop_forever() -> None:
    """The round budget is a safety net, not a rule: exceeding it is a bug."""

    class ImmortalAgent:
        def decide(self, view: PlayerView) -> Intent:
            return CastVote()  # nobody ever dies

    state = create_game(6, rng=create_rng(11))
    agents: dict[PlayerId, Agent] = {player.id: ImmortalAgent() for player in state.players}

    with pytest.raises(RuntimeError, match="did not end"):
        play_game(state, agents, max_rounds=5)
