"""Roles, nights and resolutions together, a hundred times over."""

import pytest

from lupus_ex_machina.agents.scripted import RandomAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.events import (
    NightPowerUsed,
    PriorityShared,
    ShotFired,
)
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.roles import ROLES, RoleActionName, Team
from lupus_ex_machina.engine.runner import GameResult, play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.victory import Outcome

# --- The whole thing, a hundred times (J4.7.3) -------------------------------


async def played(seed: int) -> GameResult:
    rng = create_rng(seed)
    state = create_game(rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: RandomAgent(rng=rng) for player in state.players}
    return await play_game(state, agents, journal=Journal())


@pytest.mark.parametrize("seed", range(100))
async def test_a_hundred_games_with_every_role_all_reach_a_winner(seed: int) -> None:
    """The exit criterion of the jalon, on the full table of five roles."""
    result = await played(seed)

    assert result.state.phase is Phase.ENDED
    assert result.outcome in {Outcome.VILLAGE_WINS, Outcome.WEREWOLVES_WIN}


async def test_the_corpus_actually_exercises_every_role() -> None:
    """Guard the guard: a hundred games proving nothing would still be a hundred.

    Terminating is only worth checking on games where the powers were used, so
    this fails if a role quietly stops being playable.
    """
    used: set[RoleActionName] = set()
    for seed in range(20):
        for event in (await played(seed)).journal:
            match event.payload:
                case NightPowerUsed() as power:
                    used.add(power.action)
                case PriorityShared():
                    used.add(RoleActionName.DEVOUR)
                case ShotFired():
                    used.add(RoleActionName.SHOOT)
                case _:
                    continue

    assert used == set(RoleActionName)


async def test_no_finished_game_leaves_a_hunter_owing_a_shot() -> None:
    """Every debt the rules create is settled before the game is called."""
    for seed in range(20):
        result = await played(seed)
        owing = [
            player
            for player in result.state.players
            if not player.alive
            and ROLES[player.role].on_death is not None
            and not result.state.has_spent(player.id, RoleActionName.SHOOT)
        ]

        assert owing == [], f"seed {seed} ended with an unfired shot"


async def test_the_village_and_the_pack_both_win_somewhere_in_the_corpus() -> None:
    """A corpus one side always wins would hide half the end conditions."""
    outcomes = {(await played(seed)).outcome for seed in range(30)}

    assert outcomes == {Outcome.VILLAGE_WINS, Outcome.WEREWOLVES_WIN}


async def test_a_finished_game_never_leaves_a_wolf_and_a_villager_at_parity() -> None:
    """The end condition, read back off the games it ended (D-059)."""
    for seed in range(30):
        final = (await played(seed)).state
        wolves = len(final.living_of_team(Team.WEREWOLVES))
        villagers = len(final.living_of_team(Team.VILLAGE))

        assert wolves == 0 or wolves > villagers or wolves + villagers == 2
