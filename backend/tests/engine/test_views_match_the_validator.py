"""The view and the validator must tell the same story (J4, D-001)."""

from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.intents import (
    Intent,
    IntentKind,
    PriorityPoint,
    SharePriority,
    TakeTurn,
    Vote,
    Wait,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import validate_intent
from lupus_ex_machina.engine.views import project
from support.views_games import VILLAGER, WOLF, day, game, night

# --- The view and the validator must tell the same story ---------------------


def accepts(state: GameState, actor: PlayerId, intent: Intent) -> bool:
    """Whether the validator would let this actor play this intent."""
    try:
        validate_intent(state, actor, intent)
    except IllegalIntentError:
        return False
    return True


def every_moment_of_a_game() -> list[GameState]:
    """One state per moment a view can be built from, including the closed ones."""
    a_share = (PriorityPoint(target=VILLAGER, points=50),)
    return [
        game(),
        day(number=1),
        day(),
        day().with_ballot_from(WOLF, VILLAGER),
        day().with_players_killed([VILLAGER]),
        day().reopened_for_runoff((WOLF, VILLAGER)),
        night(),
        night().with_priority_share_from(WOLF, a_share),
        night().with_players_killed([VILLAGER]),
        night().reopened_for_runoff((VILLAGER,)),
        day().entering(Phase.RESOLUTION),
        day().entering(Phase.RESOLUTION).entering(Phase.ENDED),
    ]


def test_the_view_offers_exactly_the_targets_the_validator_accepts() -> None:
    """The view is a promise, and the validator is the one that keeps it.

    A target offered but refused strands an agent on a move it was invited to
    play; a target refused but offered hands it a move the rules say does not
    exist. Both are silent until a model meets them (J7), so the two are compared
    exhaustively here, for every player — dead ones included — at every moment.
    """
    for state in every_moment_of_a_game():
        for actor in state.players:
            view = project(state, actor.id)

            for other in state.players:
                where = f"{state.phase} day {state.day}: {actor.id} -> {other.id}"
                assert (other.id in view.vote_targets) == accepts(
                    state, actor.id, TakeTurn(vote=Vote(target=other.id))
                ), f"vote, {where}"
                assert (other.id in view.action_targets) == accepts(
                    state,
                    actor.id,
                    SharePriority(allocations=(PriorityPoint(target=other.id, points=10),)),
                ), f"prey, {where}"


def test_the_view_offers_exactly_the_intent_kinds_the_validator_accepts() -> None:
    """Same promise, on the moves that need no target.

    SHARE_PRIORITY always needs one, so it is covered by the test above.
    """
    speaking = TakeTurn(speech="Je vous écoute.")
    voting = TakeTurn(vote=Vote())

    for state in every_moment_of_a_game():
        for actor in state.players:
            view = project(state, actor.id)
            where = f"at {state.phase} day {state.day}, for {actor.id}"

            may_speak = accepts(state, actor.id, speaking)
            may_vote = accepts(state, actor.id, voting)

            assert view.may_speak == may_speak, f"speaking {where}"
            assert view.may_vote == may_vote, f"voting {where}"
            assert (IntentKind.WAIT in view.allowed_intents) == accepts(state, actor.id, Wait()), (
                f"waiting {where}"
            )
            assert (IntentKind.TAKE_TURN in view.allowed_intents) == (may_speak or may_vote), (
                f"taking a turn {where}"
            )
