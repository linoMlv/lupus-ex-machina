"""What the rules make of a ballot, and of a turn at the floor (D-028)."""

import pytest

from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.intents import (
    TakeTurn,
    Vote,
    Wait,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import validate_intent
from support.validation_games import OTHER_VILLAGER, OTHER_WOLF, UNKNOWN, VILLAGER, WOLF, day, game

# --- Votes ------------------------------------------------------------------


def test_voting_for_an_unknown_player_is_refused() -> None:
    with pytest.raises(IllegalIntentError, match="Unknown"):
        validate_intent(day(), WOLF, TakeTurn(vote=Vote(target=UNKNOWN)))


def test_voting_for_oneself_is_refused() -> None:
    """The view never offers the voter to themselves, so the validator must agree.

    A model that names itself would otherwise cast a legal, lethal ballot for a
    move the rules handed to it say does not exist.
    """
    with pytest.raises(IllegalIntentError, match="themselves"):
        validate_intent(day(), WOLF, TakeTurn(vote=Vote(target=WOLF)))


def test_voting_for_a_dead_player_is_refused() -> None:
    state = day().with_players_killed([VILLAGER])

    with pytest.raises(IllegalIntentError, match="dead"):
        validate_intent(state, WOLF, TakeTurn(vote=Vote(target=VILLAGER)))


def test_a_vote_cannot_be_cast_twice() -> None:
    """A vote is irrevocable, and casting one ends the right to speak (D-013, D-024)."""
    state = day().with_ballot_from(WOLF, VILLAGER)

    with pytest.raises(IllegalIntentError, match="already voted"):
        validate_intent(state, WOLF, TakeTurn(vote=Vote(target=OTHER_VILLAGER)))


def test_speaking_after_voting_is_refused() -> None:
    state = day().with_ballot_from(WOLF, VILLAGER)

    with pytest.raises(IllegalIntentError, match="already voted"):
        validate_intent(state, WOLF, TakeTurn(speech="Un dernier mot."))


def test_a_player_who_voted_may_still_wait() -> None:
    """Voting removes speech, not existence: the agent keeps thinking (D-028)."""
    state = day().with_ballot_from(WOLF, VILLAGER)

    validate_intent(state, WOLF, Wait())


# --- The three ways a turn can go, and what the rules make of them (J5.2) ----


def test_a_turn_may_speak_and_vote_at_once() -> None:
    """The turn a player votes in is the one turn they may do both (D-028)."""
    validate_intent(day(), WOLF, TakeTurn(speech="J'ai assez entendu.", vote=Vote(target=VILLAGER)))


def test_a_turn_that_speaks_illegally_is_refused_whole() -> None:
    """Both halves have to hold, or the turn does not.

    Judging them apart would let a player who has lost the floor slip a second
    ballot in behind a sentence the rules were going to drop anyway.
    """
    state = day().with_ballot_from(WOLF, VILLAGER)

    with pytest.raises(IllegalIntentError, match="lost the floor"):
        validate_intent(state, WOLF, TakeTurn(speech="Encore un mot.", vote=Vote()))


def test_a_turn_that_votes_illegally_is_refused_even_when_it_speaks_well() -> None:
    """The mirror of the case above, and it needs a day where the two differ.

    Day 1 is that day: anyone may speak, nobody may be named (D-032). Written
    against a player who had already voted, this test passed on the *speech*
    being refused, and said nothing at all about the ballot.
    """
    first_day = game().entering(Phase.DAY, day=1)

    validate_intent(first_day, WOLF, TakeTurn(speech="Je continue."))
    with pytest.raises(IllegalIntentError, match="blank"):
        validate_intent(
            first_day, WOLF, TakeTurn(speech="Je continue.", vote=Vote(target=VILLAGER))
        )


def test_waiting_keeps_the_floor_for_later() -> None:
    """Saying nothing is a move, not a forfeit (D-048).

    It is what makes silence worth something: a player can sit out a turn and
    still answer the one after it.
    """
    validate_intent(day(), WOLF, Wait())

    validate_intent(day(), WOLF, TakeTurn(speech="Finalement, si."))


def test_one_may_not_address_or_accuse_the_dead() -> None:
    """Only the living can be named.

    The auction pays for being addressed and for being accused (D-002), so
    naming a corpse would buy a bonus nobody could ever spend.
    """
    state = day().with_players_killed([VILLAGER])

    with pytest.raises(IllegalIntentError, match="dead"):
        validate_intent(state, WOLF, TakeTurn(speech="Tu mens.", accused=VILLAGER))
    with pytest.raises(IllegalIntentError, match="dead"):
        validate_intent(state, WOLF, TakeTurn(speech="Tu mens.", addressed=VILLAGER))


def test_one_may_not_accuse_someone_who_is_not_at_the_table() -> None:
    with pytest.raises(IllegalIntentError, match="Unknown"):
        validate_intent(day(), WOLF, TakeTurn(speech="Tu mens.", accused=UNKNOWN))


# --- The silent runoff of a tied vote (J5.4.2, D-050, D-062) -----------------


def runoff(state: GameState, *targets: PlayerId) -> GameState:
    """Reopen a day as a runoff between the given players."""
    return state.reopened_for_runoff(targets)


def test_a_runoff_only_accepts_the_players_it_is_between() -> None:
    state = runoff(day(), WOLF, VILLAGER)

    validate_intent(state, OTHER_WOLF, TakeTurn(vote=Vote(target=WOLF)))
    with pytest.raises(IllegalIntentError, match="runoff"):
        validate_intent(state, OTHER_WOLF, TakeTurn(vote=Vote(target=OTHER_VILLAGER)))


def test_a_runoff_still_accepts_a_blank_vote() -> None:
    """Nothing forces a hand: the round may end with nobody eliminated (D-050)."""
    validate_intent(runoff(day(), WOLF, VILLAGER), OTHER_WOLF, TakeTurn(vote=Vote()))


def test_a_runoff_is_silent() -> None:
    """The second round is a vote, not a second debate (D-050)."""
    with pytest.raises(IllegalIntentError, match="runoff"):
        validate_intent(runoff(day(), WOLF, VILLAGER), OTHER_WOLF, TakeTurn(speech="Un mot."))


def test_a_player_at_stake_in_a_runoff_still_votes() -> None:
    """Being named does not cost the right to vote, only to vote for oneself."""
    state = runoff(day(), WOLF, VILLAGER)

    validate_intent(state, WOLF, TakeTurn(vote=Vote(target=VILLAGER)))
    with pytest.raises(IllegalIntentError, match="themselves"):
        validate_intent(state, WOLF, TakeTurn(vote=Vote(target=WOLF)))
