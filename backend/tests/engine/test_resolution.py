"""Resolving the day vote.

Every death is applied at once and the victory is evaluated only afterwards
(D-059) — checking in between would let the wolves win before a pending shot is
fired, which the reference scenarios forbid.

The night has its own module and its own tests: it collects several powers and
settles them together, where the day comes down to counting ballots.
"""

from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.resolution import resolve_day
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.state import GameState

WOLF = PlayerId("p0")
OTHER_WOLF = PlayerId("p1")
VILLAGER = PlayerId("p2")
OTHER_VILLAGER = PlayerId("p3")
THIRD_VILLAGER = PlayerId("p4")


def game() -> GameState:
    return GameState.initial(
        (
            Player(id=WOLF, name="Adèle", seat=0, role=RoleName.WEREWOLF),
            Player(id=OTHER_WOLF, name="Basile", seat=1, role=RoleName.WEREWOLF),
            Player(id=VILLAGER, name="Camille", seat=2, role=RoleName.VILLAGER),
            Player(id=OTHER_VILLAGER, name="Diane", seat=3, role=RoleName.VILLAGER),
            Player(id=THIRD_VILLAGER, name="Émile", seat=4, role=RoleName.VILLAGER),
        )
    )


# --- Day vote ---------------------------------------------------------------


def test_the_most_voted_player_is_eliminated() -> None:
    state = (
        game()
        .with_ballot_from(WOLF, VILLAGER)
        .with_ballot_from(OTHER_WOLF, VILLAGER)
        .with_ballot_from(VILLAGER, WOLF)
    )

    resolved, eliminated = resolve_day(state)

    assert eliminated == VILLAGER
    assert not resolved.is_alive(VILLAGER)
    assert len(resolved.living) == 4


def test_a_tie_eliminates_nobody() -> None:
    """A silent runoff arrives in J5; until then a tie simply spares everyone (D-050)."""
    state = game().with_ballot_from(WOLF, VILLAGER).with_ballot_from(VILLAGER, WOLF)

    resolved, eliminated = resolve_day(state)

    assert eliminated is None
    assert len(resolved.living) == 5


def test_blank_votes_do_not_count_towards_anyone() -> None:
    state = (
        game()
        .with_ballot_from(WOLF, VILLAGER)
        .with_ballot_from(OTHER_WOLF)
        .with_ballot_from(VILLAGER)
    )

    _, eliminated = resolve_day(state)

    assert eliminated == VILLAGER


def test_a_fully_blank_vote_eliminates_nobody() -> None:
    """This is what the bootstrap Day 1 always looks like (D-032)."""
    state = game().with_ballot_from(WOLF).with_ballot_from(VILLAGER)

    resolved, eliminated = resolve_day(state)

    assert eliminated is None
    assert len(resolved.living) == 5


def test_resolving_the_day_leaves_the_source_state_untouched() -> None:
    state = game().with_ballot_from(WOLF, VILLAGER).with_ballot_from(OTHER_WOLF, VILLAGER)

    resolve_day(state)

    assert state.is_alive(VILLAGER)
    assert len(state.ballots) == 2


# --- Round bookkeeping ------------------------------------------------------


def test_resolving_clears_the_choices_of_the_round() -> None:
    """Ballots belong to a round, never to the next one."""
    state = game().with_ballot_from(WOLF, VILLAGER)

    resolved, _ = resolve_day(state)

    assert resolved.ballots == ()
