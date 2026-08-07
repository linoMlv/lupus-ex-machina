"""The witch is told whom to save, and she alone (D-029)."""

from lupus_ex_machina.engine.intents import (
    PriorityPoint,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.roles import RoleActionName, RoleName
from lupus_ex_machina.engine.rules import DebateOptions, GameRules
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.views import project
from support.views_games import OTHER_VILLAGER, OTHER_WOLF, VILLAGER, WOLF

# --- The witch is told whom to save, and she alone ---------------------------


def a_night_where_the_pack_took_the_villager() -> GameState:
    """A night the pack has settled, on a table that holds a witch."""
    table = (
        Player(id=WOLF, name="Adèle", seat=0, role=RoleName.WEREWOLF),
        Player(id=OTHER_WOLF, name="Basile", seat=1, role=RoleName.WITCH),
        Player(id=VILLAGER, name="Camille", seat=2, role=RoleName.VILLAGER),
        Player(id=OTHER_VILLAGER, name="Diane", seat=3, role=RoleName.VILLAGER),
    )
    return (
        GameState.initial(table)
        .entering(Phase.DAY, day=1)
        .entering(Phase.RESOLUTION)
        .entering(Phase.NIGHT)
        .with_priority_share_from(WOLF, (PriorityPoint(target=VILLAGER, points=100),))
    )


def test_the_witch_is_told_whom_the_pack_took() -> None:
    """Her potion saves that one player and no other (D-029).

    Without this she is handed a power and no way to aim it: the view offers the
    union of what both her potions reach, which does not say which is which.
    """
    witch = OTHER_WOLF  # seated as the witch on this table

    assert project(a_night_where_the_pack_took_the_villager(), witch).victim_tonight == VILLAGER


def test_nobody_but_the_witch_is_told_whom_the_pack_took() -> None:
    """It is the pack's secret until dawn, and hers only because she answers it."""
    state = a_night_where_the_pack_took_the_villager()

    for viewer in (WOLF, VILLAGER, OTHER_VILLAGER):
        assert project(state, viewer).victim_tonight is None, viewer


def test_a_witch_out_of_life_potions_is_told_nothing() -> None:
    """Shown exactly while she can act on it, which is what the validator asks too."""
    state = a_night_where_the_pack_took_the_villager().with_power_spent_by(
        OTHER_WOLF, RoleActionName.HEAL
    )

    assert project(state, OTHER_WOLF).victim_tonight is None


def test_the_view_carries_the_word_limits_the_player_is_held_to() -> None:
    """What a model is told it may write has to come from the view (D-021, GL-3).

    The limits are a rule of the game like any other (`debate`), and the prompt
    is built from the projection alone: read anywhere else, they would be the
    one thing in a prompt the view did not carry.
    """
    rules = GameRules(
        debate=DebateOptions(speech_word_limit=12, analysis_word_limit=8, notebook_word_limit=4)
    )
    state = create_game(rules, rng=create_rng(3))

    limits = project(state, state.players[0].id).limits

    assert (limits.speech_words, limits.analysis_words, limits.notebook_words) == (12, 8, 4)
