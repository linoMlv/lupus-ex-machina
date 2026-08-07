"""An intent, judged by the rules and then applied to the state.

The one gate between what an agent wants and what the game becomes (D-001). An
intent the rules refuse costs its author a turn and nothing more — it is
recorded as refused rather than quietly ignored, so a player never believes they
acted when they did not.
"""

from typing import assert_never

from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.events import (
    BallotAnnounced,
    BallotCast,
    NightPowerUsed,
    PriorityShared,
    SpeechDelivered,
)
from lupus_ex_machina.engine.intents import Intent, RoleAction, SharePriority, TakeTurn, Wait
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.records import count_words
from lupus_ex_machina.engine.runner.scribe import Scribe
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import validate_intent


async def take_turn(scribe: Scribe, state: GameState, player: PlayerId) -> GameState:
    """Ask a player for their turn, then play what the rules will take of it.

    The two halves live together here so that no caller can do one without the
    other: asking without applying loses the move, applying without asking is
    not a move at all.
    """
    return apply(scribe, state, player, await scribe.ask(state, player))


def apply(scribe: Scribe, state: GameState, actor: PlayerId, intent: Intent) -> GameState:
    """Validate then apply. An intent refused costs its author a turn, nothing more."""
    try:
        validate_intent(state, actor, intent)
    except IllegalIntentError as refusal:
        scribe.refuse(state, actor, str(refusal))
        return state

    match intent:
        case TakeTurn():
            return _play_turn(scribe, state, actor, intent)
        case SharePriority():
            state = state.with_priority_share_from(actor, intent.allocations)
            scribe.record(PriorityShared(actor=actor, allocations=intent.allocations), at=state)
            return state
        case RoleAction():
            state = state.with_night_choice_from(actor, intent.action, intent.target)
            scribe.record(
                NightPowerUsed(actor=actor, action=intent.action, target=intent.target), at=state
            )
            return state
        case Wait():
            # Silence leaves the state untouched, and says nothing anyone could
            # act on while the floor still goes round the table. It becomes a
            # fact worth recording when the bidding does (J5).
            return state
        case _:  # pragma: no cover - the union is closed, mypy proves this is dead
            assert_never(intent)


def _play_turn(scribe: Scribe, state: GameState, actor: PlayerId, turn: TakeTurn) -> GameState:
    """Apply a turn: what was said first, then what was cast (D-051).

    The order is a rule of the game, not a detail of this function. A player may
    speak in the very turn they vote in but never after (D-028), and the table is
    told someone has voted only once they have had their say — otherwise the
    announcement would arrive before the words that explain it.
    """
    if (speech := turn.speech) is not None:
        state = _say(scribe, state, actor, speech, turn)
    if turn.vote is not None:
        state = cast(scribe, state, actor, turn.vote.target)
    return state


def _say(
    scribe: Scribe, state: GameState, speaker: PlayerId, speech: str, turn: TakeTurn
) -> GameState:
    """Record a turn at the floor, and remember the round had it.

    The journal keeps the words; the state keeps only what the next auction is
    scored against (D-002). There is one floor and it is the day's: the night is
    silent for everyone (D-083).
    """
    scribe.record(
        SpeechDelivered(
            speaker=speaker, speech=speech, addressed=turn.addressed, accused=turn.accused
        ),
        at=state,
    )
    return state.with_speech_from(
        speaker, words=count_words(speech), addressed=turn.addressed, accused=turn.accused
    )


def cast(
    scribe: Scribe, state: GameState, voter: PlayerId, target: PlayerId | None = None
) -> GameState:
    """Record a vote. The only way a ballot enters the game.

    Two facts, because the rules address two audiences: *that* someone voted
    closes the round and is public (D-051), *whom* they named stays theirs until
    the count — unless the ballot is blank, which is public at once (D-027). The
    audience of each is settled by the fact itself.
    """
    state = state.with_ballot_from(voter, target)
    scribe.record(BallotCast(voter=voter, target=target), at=state)
    scribe.record(BallotAnnounced(voter=voter), at=state)
    return state
