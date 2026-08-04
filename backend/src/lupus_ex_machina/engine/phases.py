"""Phase state machine.

The legal moves live in a table rather than in a cascade of conditions: a table
can be tested exhaustively, a cascade cannot.

Night 0 and Day 1 are phases in their own right, not special cases inside the
normal loop (D-032). So is the hunter's shot: it is fired by day and in public
even when the night killed him (D-030), so it has to be played and watched
rather than applied where the death happened.
"""

from enum import StrEnum

from lupus_ex_machina.engine.errors import IllegalTransitionError


class Phase(StrEnum):
    """Phases a game goes through."""

    NIGHT_ZERO = "night_zero"
    DAY = "day"
    NIGHT = "night"
    AVENGING_SHOT = "avenging_shot"
    RESOLUTION = "resolution"
    ENDED = "ended"


# Night 0 holds no action, so it has nothing to resolve and leads straight to the
# first day (D-032). RESOLUTION is entered twice per round — once after the day
# vote, once after the night — which is why it leads to several phases. The table
# states what is *legal*; the engine decides which of those moves to take.
LEGAL_TRANSITIONS: dict[Phase, frozenset[Phase]] = {
    Phase.NIGHT_ZERO: frozenset({Phase.DAY}),
    Phase.DAY: frozenset({Phase.RESOLUTION}),
    Phase.NIGHT: frozenset({Phase.RESOLUTION}),
    Phase.RESOLUTION: frozenset({Phase.DAY, Phase.NIGHT, Phase.ENDED, Phase.AVENGING_SHOT}),
    Phase.AVENGING_SHOT: frozenset({Phase.RESOLUTION}),
    Phase.ENDED: frozenset(),
}


def is_transition_allowed(current: Phase, following: Phase) -> bool:
    """Tell whether the game may move from one phase to the next."""
    return following in LEGAL_TRANSITIONS[current]


def ensure_transition_allowed(current: Phase, following: Phase) -> None:
    """Raise :class:`IllegalTransitionError` when the phase change is not allowed."""
    if not is_transition_allowed(current, following):
        raise IllegalTransitionError(f"Transition {current} -> {following} is not allowed")
