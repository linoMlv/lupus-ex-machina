"""Legality of intents.

The engine owns legality, not the agents (D-001): a language model produces
illegal actions routinely, so every refusal here is a rule of the game, and each
one states its reason.
"""

import contextlib

import pytest

from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.intents import (
    CastVote,
    Intent,
    RoleAction,
    RoleActionName,
    Speak,
    Wait,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import validate_intent

WOLF = PlayerId("p0")
OTHER_WOLF = PlayerId("p1")
VILLAGER = PlayerId("p2")
OTHER_VILLAGER = PlayerId("p3")
UNKNOWN = PlayerId("nobody")

DEVOUR_VILLAGER = RoleAction(action=RoleActionName.DEVOUR, target=VILLAGER)


def game() -> GameState:
    return GameState.initial(
        (
            Player(id=WOLF, name="Alice", seat=0, role=RoleName.WEREWOLF),
            Player(id=OTHER_WOLF, name="Bruno", seat=1, role=RoleName.WEREWOLF),
            Player(id=VILLAGER, name="Camille", seat=2, role=RoleName.VILLAGER),
            Player(id=OTHER_VILLAGER, name="Dounia", seat=3, role=RoleName.VILLAGER),
        )
    )


def day(state: GameState | None = None, *, number: int = 2) -> GameState:
    """Move a game to a plain debate day — day 2 has no bootstrap restriction."""
    return (state or game()).entering(Phase.DAY, day=number)


def night(state: GameState | None = None) -> GameState:
    return day(state).entering(Phase.RESOLUTION).entering(Phase.NIGHT)


# --- Actor ------------------------------------------------------------------


def test_a_dead_player_cannot_act() -> None:
    state = day().with_players_killed([VILLAGER])

    with pytest.raises(IllegalIntentError, match="dead"):
        validate_intent(state, VILLAGER, Wait())


def test_an_unknown_player_cannot_act() -> None:
    with pytest.raises(IllegalIntentError, match="Unknown"):
        validate_intent(day(), UNKNOWN, Wait())


# --- Phases -----------------------------------------------------------------


def test_night_zero_allows_nothing_but_waiting() -> None:
    """Night 0 is a bootstrap round: agents think and take notes, they do not act (D-032)."""
    state = game()

    validate_intent(state, WOLF, Wait())
    for intent in (Speak(speech="Bonsoir."), CastVote(), DEVOUR_VILLAGER):
        with pytest.raises(IllegalIntentError):
            validate_intent(state, WOLF, intent)


def test_a_role_action_is_refused_during_the_day() -> None:
    with pytest.raises(IllegalIntentError, match="night"):
        validate_intent(day(), WOLF, DEVOUR_VILLAGER)


def test_speaking_and_voting_are_refused_during_the_night() -> None:
    state = night()

    for intent in (Speak(speech="Chut."), CastVote(target=VILLAGER)):
        with pytest.raises(IllegalIntentError):
            validate_intent(state, WOLF, intent)


@pytest.mark.parametrize("phase", [Phase.RESOLUTION, Phase.ENDED])
def test_no_one_acts_while_the_engine_resolves_or_after_the_end(phase: Phase) -> None:
    state = day().entering(Phase.RESOLUTION)
    state = state if phase is Phase.RESOLUTION else state.entering(Phase.ENDED)

    with pytest.raises(IllegalIntentError):
        validate_intent(state, WOLF, Wait())


# --- Day 1 bootstrap --------------------------------------------------------


def test_day_one_only_accepts_blank_votes() -> None:
    """The first day exists to break the ice: nobody may be named yet (D-032)."""
    state = game().entering(Phase.DAY, day=1)

    validate_intent(state, WOLF, CastVote())
    with pytest.raises(IllegalIntentError, match="blank"):
        validate_intent(state, WOLF, CastVote(target=VILLAGER))


def test_later_days_accept_named_votes() -> None:
    validate_intent(day(), WOLF, CastVote(target=VILLAGER))


# --- Votes ------------------------------------------------------------------


def test_voting_for_an_unknown_player_is_refused() -> None:
    with pytest.raises(IllegalIntentError, match="Unknown"):
        validate_intent(day(), WOLF, CastVote(target=UNKNOWN))


def test_voting_for_a_dead_player_is_refused() -> None:
    state = day().with_players_killed([VILLAGER])

    with pytest.raises(IllegalIntentError, match="dead"):
        validate_intent(state, WOLF, CastVote(target=VILLAGER))


def test_a_vote_cannot_be_cast_twice() -> None:
    """A vote is irrevocable, and casting one ends the right to speak (D-013, D-024)."""
    state = day().with_ballot_from(WOLF, VILLAGER)

    with pytest.raises(IllegalIntentError, match="already voted"):
        validate_intent(state, WOLF, CastVote(target=OTHER_VILLAGER))


def test_speaking_after_voting_is_refused() -> None:
    state = day().with_ballot_from(WOLF, VILLAGER)

    with pytest.raises(IllegalIntentError, match="already voted"):
        validate_intent(state, WOLF, Speak(speech="Un dernier mot."))


def test_a_player_who_voted_may_still_wait() -> None:
    """Voting removes speech, not existence: the agent keeps thinking (D-028)."""
    state = day().with_ballot_from(WOLF, VILLAGER)

    validate_intent(state, WOLF, Wait())


# --- Night actions ----------------------------------------------------------


def test_only_a_wolf_may_devour() -> None:
    with pytest.raises(IllegalIntentError, match="werewolf"):
        validate_intent(night(), VILLAGER, DEVOUR_VILLAGER)


def test_a_wolf_may_not_devour_a_fellow_wolf() -> None:
    with pytest.raises(IllegalIntentError, match="own team"):
        validate_intent(night(), WOLF, RoleAction(action=RoleActionName.DEVOUR, target=OTHER_WOLF))


def test_a_wolf_may_not_devour_a_dead_player() -> None:
    state = night().with_players_killed([VILLAGER])

    with pytest.raises(IllegalIntentError, match="dead"):
        validate_intent(state, WOLF, DEVOUR_VILLAGER)


def test_a_wolf_designates_a_target_only_once_per_night() -> None:
    state = night().with_night_choice_from(WOLF, VILLAGER)

    with pytest.raises(IllegalIntentError, match="already"):
        validate_intent(
            state, WOLF, RoleAction(action=RoleActionName.DEVOUR, target=OTHER_VILLAGER)
        )


def test_a_legal_devouring_passes() -> None:
    validate_intent(night(), WOLF, DEVOUR_VILLAGER)


# --- Purity -----------------------------------------------------------------


@pytest.mark.parametrize(
    "intent",
    [
        Wait(),
        CastVote(target=UNKNOWN),
        Speak(speech="Bonjour."),
        DEVOUR_VILLAGER,
    ],
)
def test_validation_never_changes_the_state(intent: Intent) -> None:
    """Validating is a question, not a move: a refusal must leave no trace (J2.3.4)."""
    state = day()
    before = state.model_dump()

    with contextlib.suppress(IllegalIntentError):
        validate_intent(state, WOLF, intent)

    assert state.model_dump() == before
