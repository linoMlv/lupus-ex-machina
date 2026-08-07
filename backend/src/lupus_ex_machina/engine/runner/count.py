"""Closing a day's vote: the undecided, the runoff, the count, and the stock-taking.

Everything that happens once the debate is over. Kept apart from the debate
itself because the two answer different questions: the debate is about who gets
to speak, this is about what the table has decided.
"""

from lupus_ex_machina.engine.events import (
    BallotsRevealed,
    EventPayload,
    RevealedBallot,
    RunoffOpened,
    VoteResolved,
)
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.runner import acting
from lupus_ex_machina.engine.runner.scribe import Scribe
from lupus_ex_machina.engine.state import GameState


def vote_outcome(victims: tuple[PlayerId, ...]) -> EventPayload:
    """How a resolved day announces itself: one player eliminated, or nobody."""
    return VoteResolved(eliminated=victims[0] if victims else None)


def carry_the_undecided_to_a_blank_vote(scribe: Scribe, state: GameState) -> GameState:
    """Cast a blank ballot for everyone the round is still waiting on.

    This is how a round the table did not close itself is closed anyway (D-048,
    D-060) — and it eliminates nobody by itself: a game that does not progress is
    an admitted state, not a bug (D-078).
    """
    for player in state.living:
        if not state.has_voted(player.id):
            state = acting.cast(scribe, state, player.id)
    return state


async def hold_a_silent_runoff(
    scribe: Scribe, state: GameState, tied: tuple[PlayerId, ...]
) -> GameState:
    """Put a tied vote back to the table, once, without a word (D-050, D-062).

    No auction and no debate: the question is closed, only the answer is
    reopened. Held once — a second tie spares everyone, which is where the rule
    stops rather than asking again forever.
    """
    state = state.reopened_for_runoff(tied)
    scribe.record(RunoffOpened(targets=tied), at=state)

    for player in state.living:
        state = await acting.take_turn(scribe, state, player.id)
    return carry_the_undecided_to_a_blank_vote(scribe, state)


def read_the_count_out(scribe: Scribe, state: GameState) -> None:
    """Show the table who named whom, if the configuration allows it (D-013).

    Before the resolution rather than with it: the count is what the table reacts
    to, and what it leads to is the next fact along.
    """
    if not state.rules.information.reveal_ballots_at_the_count:
        return

    scribe.record(
        BallotsRevealed(
            ballots=tuple(
                RevealedBallot(voter=ballot.voter, target=ballot.target) for ballot in state.ballots
            )
        ),
        at=state,
    )


async def let_the_table_take_stock(scribe: Scribe, state: GameState) -> None:
    """Ask everyone left what they make of the round that just closed (D-086).

    Here and nowhere else in the round: voting ends the floor, not the thinking,
    and the count and the resolution are what teaches a player the most. Asked at
    every turn at the floor instead, this would be one large model call per
    silent player per turn (GL-7).

    Nobody is asked once the game is over — there is no next round to bring
    anything to.
    """
    await scribe.let_them_take_stock(state, tuple(player.id for player in state.living))
