"""The scenarios the rules were written from (D-049, D-059)."""

from lupus_ex_machina.agents.scripted import SilentAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.runner import play_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.victory import Outcome
from support.scenarios import AimsAt, HuntsFirst

# --- The scenario the rules were written from (J4.7.2, D-049, D-059) ---------

WOLF = PlayerId("p0")
HUNTER = PlayerId("p1")
VILLAGER = PlayerId("p2")


async def test_the_hunter_eaten_at_night_takes_the_last_wolf_with_him() -> None:
    """Le loup mange le chasseur, le chasseur tue le loup au matin, le villageois gagne.

    Word for word the scenario of D-049. It only comes out this way because the
    shot is resolved before the victory is evaluated: measured a moment earlier,
    two players are left at parity and the wolves have won.
    """
    table = (
        Player(id=WOLF, name="Adèle", seat=0, role=RoleName.WEREWOLF),
        Player(id=HUNTER, name="Basile", seat=1, role=RoleName.HUNTER),
        Player(id=VILLAGER, name="Camille", seat=2, role=RoleName.VILLAGER),
    )
    agents: dict[PlayerId, Agent] = {
        WOLF: HuntsFirst(),
        HUNTER: AimsAt(WOLF),
        VILLAGER: SilentAgent(),
    }

    result = await play_game(GameState.initial(table), agents, journal=Journal())

    assert result.outcome is Outcome.VILLAGE_WINS
    assert not result.state.player(HUNTER).alive, "the pack did take him"
    assert not result.state.player(WOLF).alive, "and he took the wolf with him"
    assert result.state.player(VILLAGER).alive


async def test_a_hunter_who_kills_one_of_two_wolves_leaves_the_game_running() -> None:
    """The second scenario of D-049: the shot answers, but it does not settle."""
    other_wolf = PlayerId("p3")
    fourth = PlayerId("p4")
    table = (
        Player(id=WOLF, name="Adèle", seat=0, role=RoleName.WEREWOLF),
        Player(id=HUNTER, name="Basile", seat=1, role=RoleName.HUNTER),
        Player(id=VILLAGER, name="Camille", seat=2, role=RoleName.VILLAGER),
        Player(id=other_wolf, name="Diane", seat=3, role=RoleName.WEREWOLF),
        Player(id=fourth, name="Émile", seat=4, role=RoleName.VILLAGER),
    )
    agents: dict[PlayerId, Agent] = {
        WOLF: HuntsFirst(),
        other_wolf: HuntsFirst(),
        HUNTER: AimsAt(WOLF),
        VILLAGER: SilentAgent(),
        fourth: SilentAgent(),
    }

    result = await play_game(GameState.initial(table), agents, journal=Journal())

    assert result.rounds >= 2, "the game did not stop on the shot"
