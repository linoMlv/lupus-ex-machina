"""Resolving the day vote.

The night has its own module: it collects several powers and settles them
together, where the day comes down to counting ballots.

Deaths are applied all at once, and the outcome is evaluated only afterwards
(D-059). Resolving death by death would let the wolves win before a pending
hunter shot is fired, which contradicts the reference scenarios.

Ties spare everyone, on both the day vote and the wolves' priority vote
(D-050). The silent runoff that precedes that outcome belongs to J5 and J4;
what is implemented here is the final word of the rule, not a shortcut.
"""

from collections import Counter
from collections.abc import Iterable

from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.state import GameState


def resolve_day(state: GameState) -> tuple[GameState, tuple[PlayerId, ...]]:
    """Count the ballots, eliminate the designated player, and close the round.

    A vote takes at most one player, but it hands back a run of them like the
    night does: both close a phase, and one shape lets the runner treat them
    alike rather than knowing which is which.
    """
    named = (ballot.target for ballot in state.ballots if ballot.target is not None)
    eliminated = _single_favourite(named)
    return _apply(state, eliminated), () if eliminated is None else (eliminated,)


def _single_favourite(targets: Iterable[PlayerId]) -> PlayerId | None:
    """Return the most designated player, or ``None`` when there is no clear one."""
    tally = Counter(targets)
    if not tally:
        return None

    (favourite, votes), *others = tally.most_common()
    if others and others[0][1] == votes:
        return None
    return favourite


def _apply(state: GameState, victim: PlayerId | None) -> GameState:
    killed = state if victim is None else state.with_players_killed([victim])
    return killed.cleared_of_round_choices()
