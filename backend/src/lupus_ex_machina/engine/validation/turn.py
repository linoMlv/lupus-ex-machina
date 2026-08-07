"""A turn at the floor: what may be said, whom it may name, and the ballot in it.

Both halves are judged, and both have to hold (D-028): a player who may speak
but has already voted cannot slip a second ballot in behind a legal sentence.
"""

from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.intents import TakeTurn, Vote
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation.actor import ensure_alive_target

# Day 1 is a bootstrap round: the debate opens with nothing to go on, so nobody
# may be named yet and a blank vote is the only way out (D-032).
BOOTSTRAP_DAY = 1


def validate_turn(state: GameState, actor: PlayerId, intent: TakeTurn) -> None:
    """Judge the parts of a turn one by one (D-028).

    Both halves have to hold for the turn to: a player who may speak but has
    already voted cannot slip a second ballot in behind a legal sentence.
    """
    if intent.speech is not None:
        _validate_speech(state, actor)
        _validate_naming(state, intent)
    if intent.vote is not None:
        validate_vote(state, actor, intent.vote)


def _validate_naming(state: GameState, intent: TakeTurn) -> None:
    """One may only address and accuse players who are at the table and alive.

    The auction pays for both (D-002), so naming a corpse would buy a bonus
    nobody could spend, and naming a stranger would buy nothing at all.
    """
    for named in (intent.addressed, intent.accused):
        if named is not None:
            ensure_alive_target(state, named)


def _validate_speech(state: GameState, actor: PlayerId) -> None:
    """The floor exists by day, and by day only (D-083).

    Nobody speaks at night, the pack included: it designates its prey in
    silence, as at a real table. The wolves meet without a word on Night 0 too
    (D-032) — the rule is the same one, held in one place.
    """
    if state.phase is not Phase.DAY:
        raise IllegalIntentError("Speaking is only allowed during the day")
    if state.runoff_targets:
        raise IllegalIntentError("A runoff is a vote, not a second debate")
    _ensure_still_holds_the_floor(state, actor)


def _ensure_still_holds_the_floor(state: GameState, actor: PlayerId) -> None:
    """Voting gives up the right to speak for the rest of the round (D-013)."""
    if state.has_voted(actor):
        raise IllegalIntentError(f"Player {actor} has already voted and lost the floor")


def validate_vote(state: GameState, actor: PlayerId, vote: Vote) -> None:
    """Judge a ballot: when it may be cast, and whom it may name."""
    if state.phase is not Phase.DAY:
        raise IllegalIntentError("Voting is only allowed during the day")
    if state.has_voted(actor):
        raise IllegalIntentError(f"Player {actor} has already voted, and a vote is final")

    if vote.target is None:
        return

    if state.day == BOOTSTRAP_DAY:
        raise IllegalIntentError("On the first day, only a blank vote is allowed")
    if vote.target == actor:
        raise IllegalIntentError(f"Player {actor} cannot vote for themselves")
    if state.runoff_targets and vote.target not in state.runoff_targets:
        raise IllegalIntentError(
            f"Player {vote.target} is not one of the players this runoff is between"
        )
    ensure_alive_target(state, vote.target)
