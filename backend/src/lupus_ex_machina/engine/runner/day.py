"""A day: the floor is auctioned over and over until the table closes the round.

Speaking is won, never handed round the table (D-002), and the round ends when
the last player votes (D-013). Those two rules are what makes a debate a debate
here — speaking costs the most in the auction that follows, and voting buys the
end of the round at the price of one's own silence.

What happens once the debate is over — the runoff, the count, the stock-taking —
is in :mod:`count`.
"""

import asyncio

from lupus_ex_machina.engine.bidding import Bid, elect
from lupus_ex_machina.engine.events import (
    FloorAuctioned,
    FloorClaimed,
    ForcedVoteReason,
    VoteForced,
)
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.resolution import resolve_day, tied_targets
from lupus_ex_machina.engine.runner import acting, closing, count
from lupus_ex_machina.engine.runner.controls import DebateControl, FloorClaim, Pacing
from lupus_ex_machina.engine.runner.scribe import Scribe
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.victory import Outcome
from lupus_ex_machina.engine.views import project


def _round_progress(state: GameState) -> tuple[int, int]:
    """What a turn at the floor can add to a round: a word said, a ballot cast.

    Read off the state rather than off the intent that was played, so a refused
    intent counts as the nothing it was (D-060).
    """
    return len(state.floor), len(state.ballots)


async def play_day(
    scribe: Scribe,
    state: GameState,
    *,
    control: DebateControl,
    claim: FloorClaim,
    pacing: Pacing | None = None,
) -> tuple[GameState, Outcome | None]:
    """Run the debate, break a tie if there is one, then resolve the vote.

    A day nobody paces never waits. Unlike the rules, which travel in the state
    precisely so that no caller can forget them (J6), a missing pace is the safe
    default rather than a disagreement: it plays the day straight through.
    """
    state = await _debate(scribe, state, control=control, claim=claim, pacing=pacing or Pacing())

    tied = tied_targets(state)
    if tied and state.rules.vote.hold_a_runoff_on_a_tie:
        state = await count.hold_a_silent_runoff(scribe, state, tied)

    count.read_the_count_out(scribe, state)
    state, outcome = await closing.close(scribe, state, resolve_day, count.vote_outcome)
    if outcome is None:
        await count.let_the_table_take_stock(scribe, state)
    return state, outcome


async def _debate(
    scribe: Scribe, state: GameState, *, control: DebateControl, claim: FloorClaim, pacing: Pacing
) -> GameState:
    """Auction the floor over and over until the round closes itself (D-013).

    The round ends when the last player votes, and nothing else ends it: that is
    the arbitrage the whole debate rests on — keep talking and leave the round
    open, or close it at the price of your own silence.

    The budget of turns is a safety net around that, not a rule of the game. It
    stops a table that never votes from spending an unbounded number of model
    calls (GL-7); the ways a debate is *meant* to end are in J5.5.
    """
    for _ in range(_turn_budget(state)):
        if _everyone_voted(state):
            return state
        if control.is_out_of_turns:
            return _force_the_vote(scribe, state, ForcedVoteReason.MODERATOR)

        await pacing.before_a_turn(recorded=len(scribe.events))

        state, acted = await _auction_the_floor(scribe, state, claim=claim)
        control.spend_a_turn()
        if not acted:
            return _force_the_vote(scribe, state, ForcedVoteReason.DEBATE_EXHAUSTED)

    return _force_the_vote(scribe, state, ForcedVoteReason.TURN_BUDGET_SPENT)


def _turn_budget(state: GameState) -> int:
    """How many turns at the floor a single day may hold at the very most."""
    return state.rules.debate.turns_per_player_per_day * len(state.living)


def _everyone_voted(state: GameState) -> bool:
    """Whether the round has closed itself — the only ending that is a rule (D-013)."""
    return all(state.has_voted(player.id) for player in state.living)


def _force_the_vote(scribe: Scribe, state: GameState, reason: ForcedVoteReason) -> GameState:
    """Close a round the table did not close itself (D-048, D-060).

    Recorded before the ballots it produces: reading the journal, a blank vote
    from everyone at once means nothing without the line that says why it was
    called.
    """
    scribe.record(VoteForced(reason=reason), at=state)
    return count.carry_the_undecided_to_a_blank_vote(scribe, state)


async def _auction_the_floor(
    scribe: Scribe, state: GameState, *, claim: FloorClaim
) -> tuple[GameState, bool]:
    """Ask who wants to speak, and let the winner take their turn (D-002).

    Reports whether the turn *did* anything — a word or a ballot — which is how
    the caller tells a debate that is still going from one that has run out of
    things to say (D-060). Winning the floor and then waiting counts for nothing,
    and so does an intent the rules refused: what matters is whether the round
    moved, not whether somebody was asked.
    """
    speaker = _claimed_floor(scribe, state, claim) or await _won_floor(scribe, state)
    if speaker is None:
        return state, False

    before = _round_progress(state)
    state = await acting.take_turn(scribe, state, speaker)
    return state, _round_progress(state) != before


def _claimed_floor(scribe: Scribe, state: GameState, claim: FloorClaim) -> PlayerId | None:
    """Whoever pressed the priority button, when they may still speak (D-014).

    A claim from a player the round has nothing left to offer — dead, or already
    voted — is dropped rather than held: it was made about a turn that no longer
    exists.
    """
    claimed = claim.take()
    if claimed is None or not project(state, claimed).may_speak:
        return None

    scribe.record(FloorClaimed(player=claimed), at=state)
    return claimed


async def _won_floor(scribe: Scribe, state: GameState) -> PlayerId | None:
    """Hold an auction and hand back whoever won it, if anyone did."""
    auction = elect(
        await _bids_of(scribe, state),
        floor=state.floor,
        rules=state.rules.debate,
        rng=scribe.rng,
    )
    scribe.record(FloorAuctioned(scores=auction.scores, winner=auction.winner), at=state)
    return auction.winner


async def _bids_of(scribe: Scribe, state: GameState) -> dict[PlayerId, Bid]:
    """Ask everyone who still holds the floor how badly they want it.

    All at once, and this is where the budget of a game is won or lost: a turn at
    the floor costs about seven bids, so asking in sequence would stack seven
    latencies where one is enough (GL-7). The order of the answers is the order
    they were asked in, whatever order they come back in, so an auction stays
    reproducible.

    Whoever just spoke is not asked (D-002). The recency penalty would very
    likely have settled it anyway, but not asking is also one model call saved
    per turn, on the one call a game makes most often.
    """
    just_spoke = state.floor[-1].speaker if state.floor else None
    bidders = tuple(
        player.id
        for player in state.living
        if not state.has_voted(player.id) and player.id != just_spoke
    )
    bids = await asyncio.gather(*(scribe.bid_of(state, bidder) for bidder in bidders))
    return dict(zip(bidders, bids, strict=True))
