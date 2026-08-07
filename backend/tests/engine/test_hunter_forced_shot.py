"""A shot nobody aimed, and a shot given up (D-055)."""

import pytest

from lupus_ex_machina.agents.scripted import AlwaysAccuseAgent, SilentAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.events import ShotFired
from lupus_ex_machina.engine.hunter import someone_to_take_along
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.rules import GameRules, RoleOptions
from lupus_ex_machina.engine.runner import GameResult, play_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import validate_intent
from support.shots import (
    HUNTER,
    MANDATORY,
    OPTIONAL,
    SEER,
    TABLE,
    VILLAGER,
    WOLF,
    dying_hunter,
    shot,
)

# --- A shot nobody aimed (D-055) ---------------------------------------------


def test_by_default_the_shot_cannot_be_given_up() -> None:
    assert RoleOptions().hunter_must_shoot is True


def test_a_mandatory_shot_finds_a_target_on_its_own() -> None:
    """Non-renounceable means the engine fires when the hunter will not (D-055)."""
    assert someone_to_take_along(dying_hunter(), HUNTER) == WOLF


def test_the_engine_never_aims_at_the_hunter_himself() -> None:
    taken = someone_to_take_along(dying_hunter(), HUNTER)

    assert taken != HUNTER


def test_the_engine_never_aims_at_the_dead() -> None:
    state = dying_hunter().with_players_killed([WOLF])

    assert someone_to_take_along(state, HUNTER) == SEER


def test_a_shot_with_nobody_left_to_hit_takes_nobody() -> None:
    """Defensive: the last player standing has no one to take along."""
    state = dying_hunter().with_players_killed([WOLF, SEER, VILLAGER])

    assert someone_to_take_along(state, HUNTER) is None


def test_the_engine_picks_the_same_target_on_every_run() -> None:
    """Deterministic, so a game replays identically (D-040)."""
    state = dying_hunter()

    assert len({someone_to_take_along(state, HUNTER) for _ in range(5)}) == 1


def test_an_optional_shot_may_be_given_up() -> None:
    """The configuration can hand the choice back (D-055)."""
    assert OPTIONAL.roles.hunter_must_shoot is False


def test_a_living_hunter_in_the_shot_phase_has_no_shot_to_fire() -> None:
    """Owing a shot is what allows one, and only a death creates the debt."""
    state = (
        GameState.initial(TABLE)
        .entering(Phase.DAY, day=2)
        .entering(Phase.RESOLUTION)
        .with_players_killed([SEER])
        .entering(Phase.AVENGING_SHOT)
    )

    with pytest.raises(IllegalIntentError, match="no shot to fire"):
        validate_intent(state, HUNTER, shot(WOLF))


# --- A shot given up (D-055) -------------------------------------------------

A_TABLE_LED_BY_A_HUNTER = (
    Player(id=HUNTER, name="Adèle", seat=0, role=RoleName.HUNTER),
    Player(id=WOLF, name="Basile", seat=1, role=RoleName.WEREWOLF),
    Player(id=SEER, name="Camille", seat=2, role=RoleName.SEER),
    Player(id=VILLAGER, name="Diane", seat=3, role=RoleName.VILLAGER),
    Player(id=PlayerId("p4"), name="Émile", seat=4, role=RoleName.WITCH),
    Player(id=PlayerId("p5"), name="Faustine", seat=5, role=RoleName.VILLAGER),
)


async def a_game_where_the_hunter_is_lynched(rules: GameRules) -> GameResult:
    """Everyone accuses the lowest seat, which is the hunter; he never aims."""
    agents: dict[PlayerId, Agent] = {
        player.id: SilentAgent() if player.id == HUNTER else AlwaysAccuseAgent()
        for player in A_TABLE_LED_BY_A_HUNTER
    }
    return await play_game(
        GameState.initial(A_TABLE_LED_BY_A_HUNTER, rules=rules),
        agents,
        journal=Journal(),
    )


async def test_a_hunter_who_will_not_aim_is_aimed_for() -> None:
    """Non-renounceable means the shot happens anyway (D-055)."""
    result = await a_game_where_the_hunter_is_lynched(MANDATORY)
    fired = [event.payload for event in result.journal if isinstance(event.payload, ShotFired)]

    assert fired, "the engine fired for him"
    assert fired[0].hunter == HUNTER
    assert fired[0].chosen_by_the_hunter is False


async def test_a_hunter_who_declines_an_optional_shot_takes_nobody() -> None:
    result = await a_game_where_the_hunter_is_lynched(OPTIONAL)

    assert not [event for event in result.journal if isinstance(event.payload, ShotFired)]
    assert not result.state.player(HUNTER).alive, "he was lynched all the same"
