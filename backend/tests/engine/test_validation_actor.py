"""Who may act, and when: the actor, the phase, and the bootstrap day."""

import pytest

from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.intents import (
    TakeTurn,
    Vote,
    Wait,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.validation import validate_intent
from support.validation_games import DEVOUR_VILLAGER, UNKNOWN, VILLAGER, WOLF, day, game, night

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
    for intent in (TakeTurn(speech="Bonsoir."), TakeTurn(vote=Vote()), DEVOUR_VILLAGER):
        with pytest.raises(IllegalIntentError):
            validate_intent(state, WOLF, intent)


def test_a_role_action_is_refused_during_the_day() -> None:
    with pytest.raises(IllegalIntentError, match="not played during"):
        validate_intent(day(), WOLF, DEVOUR_VILLAGER)


def test_voting_is_refused_during_the_night() -> None:
    with pytest.raises(IllegalIntentError):
        validate_intent(night(), WOLF, TakeTurn(vote=Vote(target=VILLAGER)))


def test_nobody_speaks_at_night_the_pack_included() -> None:
    """The wolves designate their prey in silence, as at a real table (D-083).

    They had a channel of their own until 2026-08-05 (D-007, revoked): a wolf
    gets one gesture a night, so speaking meant giving up any say in the prey.
    """
    for player in (WOLF, VILLAGER):
        with pytest.raises(IllegalIntentError, match="only allowed during the day"):
            validate_intent(night(), player, TakeTurn(speech="On prend Camille."))


def test_the_pack_meets_in_silence_on_night_zero() -> None:
    """They recognise each other without a word (D-032)."""
    with pytest.raises(IllegalIntentError):
        validate_intent(game(), WOLF, TakeTurn(speech="Salut, collègue."))


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

    validate_intent(state, WOLF, TakeTurn(vote=Vote()))
    with pytest.raises(IllegalIntentError, match="blank"):
        validate_intent(state, WOLF, TakeTurn(vote=Vote(target=VILLAGER)))


def test_later_days_accept_named_votes() -> None:
    validate_intent(day(), WOLF, TakeTurn(vote=Vote(target=VILLAGER)))
