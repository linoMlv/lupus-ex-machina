"""What the roles do to each other.

The scenarios the project owner wrote out in D-049 and D-059 are the acceptance
test of this jalon: they are the reason the shot is resolved before the victory
is looked at, and the reason the night settles everything in one go. If the
engine disagrees with them, the engine is wrong.
"""

import pytest

from lupus_ex_machina.agents.scripted import RandomAgent, SilentAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.events import NightPowerUsed, PriorityShared, ShotFired
from lupus_ex_machina.engine.intents import (
    Intent,
    IntentKind,
    PriorityPoint,
    RoleAction,
    SharePriority,
    TakeTurn,
    Vote,
    Wait,
)
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.night import resolve_night
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.policy import InformationPolicy
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.roles import ROLES, RoleActionName, RoleName, Team
from lupus_ex_machina.engine.runner import GameResult, play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.victory import Outcome
from lupus_ex_machina.engine.views import PlayerView

DISCREET = InformationPolicy()


# --- Agents built for one scenario each --------------------------------------


class HuntsFirst:
    """A wolf that always puts its whole budget on the lowest-seated prey."""

    def bid(self, view: PlayerView) -> Bid:
        """Bid flatly: what this agent is for is what it does with the floor."""
        return Bid(urgency=50, intention="Jouer.")

    def decide(self, view: PlayerView) -> Intent:
        """Weigh the first prey, otherwise stay out of the way."""
        if IntentKind.SHARE_PRIORITY in view.allowed_intents and view.action_targets:
            return SharePriority(
                allocations=(
                    PriorityPoint(target=view.action_targets[0], points=view.priority_budget),
                )
            )
        if view.may_vote:
            return TakeTurn(vote=Vote())
        return Wait()


class AimsAt:
    """Someone who fires at a named player, and otherwise keeps quiet."""

    def __init__(self, target: PlayerId) -> None:
        """Take the player this agent will shoot when it gets the chance."""
        self._target = target

    def bid(self, view: PlayerView) -> Bid:
        """Bid flatly: what this agent is for is what it does with the floor."""
        return Bid(urgency=50, intention="Jouer.")

    def decide(self, view: PlayerView) -> Intent:
        """Shoot the named player, otherwise vote blank or wait."""
        if RoleActionName.SHOOT in view.available_actions and self._target in view.action_targets:
            return RoleAction(action=RoleActionName.SHOOT, target=self._target)
        if view.may_vote:
            return TakeTurn(vote=Vote())
        return Wait()


# --- The scenario the rules were written from (J4.7.2, D-049, D-059) ---------

WOLF = PlayerId("p0")
HUNTER = PlayerId("p1")
VILLAGER = PlayerId("p2")


def test_the_hunter_eaten_at_night_takes_the_last_wolf_with_him() -> None:
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

    result = play_game(GameState.initial(table), agents, journal=Journal(), policy=DISCREET)

    assert result.outcome is Outcome.VILLAGE_WINS
    assert not result.state.player(HUNTER).alive, "the pack did take him"
    assert not result.state.player(WOLF).alive, "and he took the wolf with him"
    assert result.state.player(VILLAGER).alive


def test_a_hunter_who_kills_one_of_two_wolves_leaves_the_game_running() -> None:
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

    result = play_game(GameState.initial(table), agents, journal=Journal(), policy=DISCREET)

    assert result.rounds >= 2, "the game did not stop on the shot"


# --- Potions against the night (J4.7.1) --------------------------------------

PACK = PlayerId("w0")
WITCH = PlayerId("w1")
PREY = PlayerId("v2")
OTHER_PREY = PlayerId("v3")

A_TABLE_WITH_A_WITCH = (
    Player(id=PACK, name="Adèle", seat=0, role=RoleName.WEREWOLF),
    Player(id=WITCH, name="Basile", seat=1, role=RoleName.WITCH),
    Player(id=PREY, name="Camille", seat=2, role=RoleName.VILLAGER),
    Player(id=OTHER_PREY, name="Diane", seat=3, role=RoleName.VILLAGER),
)


def a_night_where_the_pack_took(target: PlayerId) -> GameState:
    return (
        GameState.initial(A_TABLE_WITH_A_WITCH)
        .entering(Phase.DAY, day=1)
        .entering(Phase.RESOLUTION)
        .entering(Phase.NIGHT)
        .with_priority_share_from(PACK, (PriorityPoint(target=target, points=100),))
    )


def test_the_potion_of_life_answers_the_bite() -> None:
    state = a_night_where_the_pack_took(PREY).with_night_choice_from(
        WITCH, RoleActionName.HEAL, PREY
    )

    resolved, victims = resolve_night(state, policy=DISCREET)

    assert victims == ()
    assert len(resolved.living) == len(A_TABLE_WITH_A_WITCH)


def test_the_witch_taken_by_the_pack_can_save_herself() -> None:
    """The only night she survives, and the reason the potion may target her (D-029)."""
    state = a_night_where_the_pack_took(WITCH).with_night_choice_from(
        WITCH, RoleActionName.HEAL, WITCH
    )

    resolved, victims = resolve_night(state, policy=DISCREET)

    assert victims == ()
    assert resolved.is_alive(WITCH)


def test_poisoning_the_player_the_pack_already_took_kills_them_once() -> None:
    """Two claims on one player, one death — the run of victims holds no duplicate."""
    state = a_night_where_the_pack_took(PREY).with_night_choice_from(
        WITCH, RoleActionName.POISON, PREY
    )

    resolved, victims = resolve_night(state, policy=DISCREET)

    assert victims == (PREY,)
    assert len(resolved.living) == len(A_TABLE_WITH_A_WITCH) - 1


def test_a_night_can_take_the_pack_s_prey_and_the_poisoned_one() -> None:
    state = a_night_where_the_pack_took(PREY).with_night_choice_from(
        WITCH, RoleActionName.POISON, OTHER_PREY
    )

    _, victims = resolve_night(state, policy=DISCREET)

    assert set(victims) == {PREY, OTHER_PREY}


# --- The whole thing, a hundred times (J4.7.3) -------------------------------


def played(seed: int) -> GameResult:
    rng = create_rng(seed)
    state = create_game(8, rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: RandomAgent(rng=rng) for player in state.players}
    return play_game(state, agents, journal=Journal())


@pytest.mark.parametrize("seed", range(100))
def test_a_hundred_games_with_every_role_all_reach_a_winner(seed: int) -> None:
    """The exit criterion of the jalon, on the full table of five roles."""
    result = played(seed)

    assert result.state.phase is Phase.ENDED
    assert result.outcome in {Outcome.VILLAGE_WINS, Outcome.WEREWOLVES_WIN}


def test_the_corpus_actually_exercises_every_role() -> None:
    """Guard the guard: a hundred games proving nothing would still be a hundred.

    Terminating is only worth checking on games where the powers were used, so
    this fails if a role quietly stops being playable.
    """
    used: set[RoleActionName] = set()
    for seed in range(20):
        for event in played(seed).journal:
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


def test_no_finished_game_leaves_a_hunter_owing_a_shot() -> None:
    """Every debt the rules create is settled before the game is called."""
    for seed in range(20):
        result = played(seed)
        owing = [
            player
            for player in result.state.players
            if not player.alive
            and ROLES[player.role].on_death is not None
            and not result.state.has_spent(player.id, RoleActionName.SHOOT)
        ]

        assert owing == [], f"seed {seed} ended with an unfired shot"


def test_the_village_and_the_pack_both_win_somewhere_in_the_corpus() -> None:
    """A corpus one side always wins would hide half the end conditions."""
    outcomes = {played(seed).outcome for seed in range(30)}

    assert outcomes == {Outcome.VILLAGE_WINS, Outcome.WEREWOLVES_WIN}


def test_a_finished_game_never_leaves_a_wolf_and_a_villager_at_parity() -> None:
    """The end condition, read back off the games it ended (D-059)."""
    for seed in range(30):
        final = played(seed).state
        wolves = len(final.living_of_team(Team.WEREWOLVES))
        villagers = len(final.living_of_team(Team.VILLAGE))

        assert wolves == 0 or wolves > villagers or wolves + villagers == 2
