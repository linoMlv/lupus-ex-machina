"""The hunter (D-030, D-049, D-055).

He fires as he dies, always by day and in front of everyone — even when it was
the night that killed him, in which case the shot happens before the debate
opens. The shot is a phase of its own rather than an effect applied where the
death occurred: it has to be played, watched and staged, and an effect crossing
a phase boundary would be none of those.

The order matters more than anything else here. The shot is resolved **before**
the victory is evaluated (D-049), which is what makes the reference scenario of
D-059 come out the way its author says it does.
"""

import pytest

from lupus_ex_machina.agents.scripted import AlwaysAccuseAgent, SilentAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.events import ShotFired
from lupus_ex_machina.engine.hunter import hunters_owing_a_shot, someone_to_take_along
from lupus_ex_machina.engine.intents import RoleAction, Wait
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleActionName, RoleName
from lupus_ex_machina.engine.rules import GameRules, RoleOptions
from lupus_ex_machina.engine.runner import GameResult, play_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import validate_intent

HUNTER = PlayerId("p0")
WOLF = PlayerId("p1")
SEER = PlayerId("p2")
VILLAGER = PlayerId("p3")

TABLE = (
    Player(id=HUNTER, name="Adèle", seat=0, role=RoleName.HUNTER),
    Player(id=WOLF, name="Basile", seat=1, role=RoleName.WEREWOLF),
    Player(id=SEER, name="Camille", seat=2, role=RoleName.SEER),
    Player(id=VILLAGER, name="Diane", seat=3, role=RoleName.VILLAGER),
)

MANDATORY = GameRules()
OPTIONAL = GameRules(roles=RoleOptions(hunter_must_shoot=False))


def shot(target: PlayerId) -> RoleAction:
    return RoleAction(action=RoleActionName.SHOOT, target=target)


def dying_hunter() -> GameState:
    """The moment the hunter is dead and the shot is about to be fired."""
    return (
        GameState.initial(TABLE)
        .entering(Phase.DAY, day=2)
        .entering(Phase.RESOLUTION)
        .with_players_killed([HUNTER])
        .entering(Phase.AVENGING_SHOT)
    )


# --- Who owes a shot ---------------------------------------------------------


def test_a_dead_hunter_owes_a_shot() -> None:
    assert [player.id for player in hunters_owing_a_shot(dying_hunter())] == [HUNTER]


def test_a_living_hunter_owes_nothing() -> None:
    state = GameState.initial(TABLE).entering(Phase.DAY, day=2)

    assert hunters_owing_a_shot(state) == ()


def test_a_hunter_who_already_fired_owes_nothing() -> None:
    """The trigger fires once, which is also what stops two hunters looping."""
    state = dying_hunter().with_power_spent_by(HUNTER, RoleActionName.SHOOT)

    assert hunters_owing_a_shot(state) == ()


def test_nobody_else_takes_anyone_along() -> None:
    state = (
        GameState.initial(TABLE)
        .entering(Phase.DAY, day=2)
        .entering(Phase.RESOLUTION)
        .with_players_killed([SEER, VILLAGER])
        .entering(Phase.AVENGING_SHOT)
    )

    assert hunters_owing_a_shot(state) == ()


# --- Firing (J4.6.1, J4.6.4) -------------------------------------------------


def test_the_hunter_may_shoot_a_living_player() -> None:
    validate_intent(dying_hunter(), HUNTER, shot(WOLF))


def test_a_dead_hunter_owing_a_shot_is_the_one_dead_player_who_may_act() -> None:
    """Everybody else who died stays out of it, in that phase as in any other.

    Whether he *may* decline is not a matter of legality but of configuration
    (D-055): when the shot is non-renounceable, the engine fires for him.
    """
    validate_intent(dying_hunter(), HUNTER, Wait())

    state = dying_hunter().with_players_killed([SEER])
    with pytest.raises(IllegalIntentError, match="dead"):
        validate_intent(state, SEER, Wait())


def test_the_hunter_may_not_shoot_the_dead() -> None:
    state = dying_hunter().with_players_killed([WOLF])

    with pytest.raises(IllegalIntentError, match="dead"):
        validate_intent(state, HUNTER, shot(WOLF))


def test_the_hunter_may_not_shoot_himself() -> None:
    with pytest.raises(IllegalIntentError, match="themselves"):
        validate_intent(dying_hunter(), HUNTER, shot(HUNTER))


def test_nobody_but_a_hunter_may_fire() -> None:
    with pytest.raises(IllegalIntentError, match="cannot shoot"):
        validate_intent(dying_hunter(), WOLF, shot(SEER))


def test_the_shot_belongs_to_its_own_phase() -> None:
    """Fired by day and in public (D-030), never in the middle of the night."""
    night = (
        GameState.initial(TABLE)
        .entering(Phase.DAY, day=1)
        .entering(Phase.RESOLUTION)
        .entering(Phase.NIGHT)
    )

    with pytest.raises(IllegalIntentError):
        validate_intent(night, HUNTER, shot(WOLF))


def test_a_hunter_fires_once() -> None:
    """Having fired, he is a dead player like any other."""
    state = dying_hunter().with_power_spent_by(HUNTER, RoleActionName.SHOOT)

    with pytest.raises(IllegalIntentError, match="dead"):
        validate_intent(state, HUNTER, shot(WOLF))


def test_a_living_hunter_has_nothing_to_fire() -> None:
    """The shot answers a death; there is no phase for it while he is alive."""
    alive = GameState.initial(TABLE).entering(Phase.DAY, day=2)

    with pytest.raises(IllegalIntentError, match="not played during"):
        validate_intent(alive, HUNTER, shot(WOLF))


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
