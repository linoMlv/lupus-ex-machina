"""What the schema refuses, and why (J6.1.3, J6.1.4).

Two kinds of refusal live here. Bounds — a table of four, a negative word limit
— are said by the field itself. The others are said by the *model*, because they
are not wrong on their own: a seat number is wrong for the mode it comes with, a
composition is wrong for the table it is dealt to, a wake order is wrong for the
role that reads what another one chose.

The messages are French: a refused configuration is shown to whoever wrote it.
"""

import pytest
from pydantic import ValidationError

from lupus_ex_machina.engine.composition import Composition
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.rules import (
    DebateOptions,
    GameMode,
    NightOptions,
    TableOptions,
)

SIX_ROLES = (
    RoleName.WEREWOLF,
    RoleName.SEER,
    RoleName.WITCH,
    RoleName.HUNTER,
    RoleName.VILLAGER,
    RoleName.VILLAGER,
)

# --- Bounds ------------------------------------------------------------------


@pytest.mark.parametrize("player_count", [0, 1, 5, 9, 20])
def test_a_table_v1_does_not_deal_is_refused(player_count: int) -> None:
    """Six to eight, eight being the hard maximum of V1 (D-056)."""
    with pytest.raises(ValidationError):
        TableOptions(player_count=player_count)


@pytest.mark.parametrize("limit", [0, -1])
def test_a_word_limit_of_nothing_is_refused(limit: int) -> None:
    """A bubble of no words is not a shorter speech, it is no speech (D-021)."""
    with pytest.raises(ValidationError):
        DebateOptions(speech_word_limit=limit)


@pytest.mark.parametrize("urgency", [-1, 101])
def test_an_urgency_threshold_outside_the_scale_is_refused(urgency: int) -> None:
    """A bid runs from 0 to 100, so a threshold outside it means nothing."""
    with pytest.raises(ValidationError):
        DebateOptions(minimum_urgency=urgency)


def test_a_pack_that_shares_nothing_is_refused() -> None:
    """A budget of zero points is a designation nobody can weigh in on (D-008)."""
    with pytest.raises(ValidationError):
        NightOptions(priority_budget=0)


# --- A seat only means something with a mode (D-039, D-045) -------------------


def test_a_player_who_does_not_say_where_they_sit_is_refused() -> None:
    with pytest.raises(ValidationError, match="quel siège"):
        TableOptions(mode=GameMode.PLAYER)


def test_a_spectator_who_claims_a_seat_is_refused() -> None:
    """Watching and sitting down are two different games (D-045)."""
    with pytest.raises(ValidationError, match="spectateur"):
        TableOptions(human_seat=2)


def test_a_seat_beyond_the_table_is_refused() -> None:
    with pytest.raises(ValidationError, match="n'existe pas"):
        TableOptions(player_count=6, mode=GameMode.PLAYER, human_seat=6)


def test_the_last_seat_of_the_table_is_a_seat_like_any_other() -> None:
    """Seats are counted from zero, so the boundary is worth pinning down."""
    assert TableOptions(player_count=6, mode=GameMode.PLAYER, human_seat=5).human_seat == 5


# --- A composition is dealt to a table (D-061) --------------------------------


def test_a_composition_that_does_not_fill_the_table_is_refused() -> None:
    """Otherwise the deal would silently follow one of the two and drop the other."""
    with pytest.raises(ValidationError, match="6 rôles pour 8 joueurs"):
        TableOptions(composition=Composition(roles=SIX_ROLES))


def test_a_composition_that_fills_the_table_is_taken_as_given() -> None:
    table = TableOptions(player_count=6, composition=Composition(roles=SIX_ROLES))

    assert table.composition is not None
    assert table.composition.roles == SIX_ROLES


def test_a_composition_of_a_game_already_won_is_refused() -> None:
    """Asked of the victory rule itself rather than of a copy of it (D-059)."""
    with pytest.raises(ValidationError):
        Composition(roles=(RoleName.VILLAGER,) * 6)


# --- The night calls every role that wakes, in an order that works (D-006) ----


def test_a_wake_order_that_leaves_out_a_role_that_acts_is_refused() -> None:
    """A power the game never offers is an incoherent table, not a variant."""
    with pytest.raises(ValidationError, match="manquants"):
        NightOptions(wake_order=(RoleName.SEER, RoleName.WEREWOLF))


def test_a_wake_order_that_calls_a_sleeping_role_is_refused() -> None:
    """The hunter fires by day and in front of everyone (D-030)."""
    with pytest.raises(ValidationError, match="en trop"):
        NightOptions(wake_order=(RoleName.SEER, RoleName.WEREWOLF, RoleName.WITCH, RoleName.HUNTER))


def test_a_role_called_twice_in_one_night_is_refused() -> None:
    with pytest.raises(ValidationError, match="qu'une fois"):
        NightOptions(wake_order=(RoleName.SEER, RoleName.WEREWOLF, RoleName.WITCH, RoleName.WITCH))


def test_waking_the_witch_before_the_pack_is_refused() -> None:
    """She is shown the prey (D-029), so before it she would answer nothing."""
    with pytest.raises(ValidationError, match="réveillée après"):
        NightOptions(wake_order=(RoleName.SEER, RoleName.WITCH, RoleName.WEREWOLF))


def test_the_night_may_still_be_reordered_where_it_makes_sense() -> None:
    """The seer is free to move: nothing she reads depends on the pack."""
    reordered = NightOptions(wake_order=(RoleName.WEREWOLF, RoleName.WITCH, RoleName.SEER))

    assert reordered.wake_order[0] is RoleName.WEREWOLF
