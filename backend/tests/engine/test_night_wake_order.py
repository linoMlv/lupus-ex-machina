"""Who is woken, when, and why nothing settles before dawn (D-006)."""

from lupus_ex_machina.engine.night import (
    night_callers,
    resolve_night,
)
from lupus_ex_machina.engine.roles import RoleName
from support.nights import OTHER_WOLF, SEER, TABLE, VILLAGER, WOLF, forced_night, night, shared

# --- Who is woken, and when (J4.2.1) -----------------------------------------


def test_the_night_calls_the_seer_then_the_pack_then_the_witch() -> None:
    """The order is a rule: the witch must see a victim the pack has designated.

    Those who hold a power come first, in that order. Everyone else has a turn
    too (D-084) — see ``test_night_turn.py`` — but their place in the queue is a
    sweep by seat rather than a ranking.
    """
    called = [player.role for player in night_callers(night())][:4]

    assert called == [
        RoleName.SEER,
        RoleName.WEREWOLF,
        RoleName.WEREWOLF,
        RoleName.WITCH,
    ]


def test_the_roles_with_no_power_come_after_the_ones_that_have_one() -> None:
    """The hunter fires by day and in public, even when the night killed them (D-030)."""
    called = [player.role for player in night_callers(night())]

    assert called[4:] == [RoleName.HUNTER, RoleName.VILLAGER]


def test_the_night_never_wakes_the_dead() -> None:
    state = night().with_players_killed([SEER])

    assert SEER not in {player.id for player in night_callers(state)}


def test_wolves_are_woken_in_seat_order_within_their_turn() -> None:
    """A stable order, so a game replays the same way twice."""
    wolves = [player.id for player in night_callers(night()) if player.role is RoleName.WEREWOLF]

    assert wolves == [WOLF, OTHER_WOLF]


# --- Nothing happens before the end of the night (J4.2.2, J4.2.3) ------------


def test_recording_a_share_kills_nobody() -> None:
    """The whole reason the night is resolved in one go (D-006)."""
    state = shared(forced_night(), WOLF, p5=100)

    assert state.is_alive(VILLAGER)
    assert len(state.living) == len(TABLE)


def test_the_victim_only_dies_when_the_night_is_resolved() -> None:
    state = shared(shared(night(), WOLF, p5=60), OTHER_WOLF, p5=40)

    resolved, victims = resolve_night(state)

    assert victims == (VILLAGER,)
    assert not resolved.is_alive(VILLAGER)


def test_resolving_a_night_clears_what_it_collected() -> None:
    state = shared(night(), WOLF, p5=100)

    resolved, _ = resolve_night(state)

    assert resolved.priority_shares == ()
    assert resolved.runoff_targets == ()


def test_a_night_nobody_acted_in_takes_nobody() -> None:
    resolved, victims = resolve_night(night())

    assert victims == ()
    assert len(resolved.living) == len(TABLE)
