"""Phase state machine.

The legal moves are checked exhaustively: every ordered pair of phases is either
in the expected set or refused. A table can be covered that way, a cascade of
conditions cannot.
"""

import itertools

import pytest

from lupus_ex_machina.engine.errors import IllegalTransitionError
from lupus_ex_machina.engine.phases import (
    Phase,
    ensure_transition_allowed,
    is_transition_allowed,
)

# Night 0 carries no action, so it has nothing to resolve and leads straight to
# the first day (D-032). RESOLUTION is entered twice per round — after the day
# vote and after the night — hence its several exits.
EXPECTED_TRANSITIONS = {
    (Phase.NIGHT_ZERO, Phase.DAY),
    (Phase.DAY, Phase.RESOLUTION),
    (Phase.NIGHT, Phase.RESOLUTION),
    (Phase.RESOLUTION, Phase.DAY),
    (Phase.RESOLUTION, Phase.NIGHT),
    (Phase.RESOLUTION, Phase.ENDED),
}


@pytest.mark.parametrize(("current", "following"), sorted(EXPECTED_TRANSITIONS))
def test_expected_transitions_are_allowed(current: Phase, following: Phase) -> None:
    assert is_transition_allowed(current, following)
    ensure_transition_allowed(current, following)


@pytest.mark.parametrize(
    ("current", "following"),
    sorted(set(itertools.product(Phase, repeat=2)) - EXPECTED_TRANSITIONS),
)
def test_every_other_transition_is_refused(current: Phase, following: Phase) -> None:
    assert not is_transition_allowed(current, following)
    with pytest.raises(IllegalTransitionError):
        ensure_transition_allowed(current, following)


def test_the_ended_phase_is_terminal() -> None:
    assert not any(is_transition_allowed(Phase.ENDED, phase) for phase in Phase)


def test_no_phase_transitions_to_itself() -> None:
    assert not any(is_transition_allowed(phase, phase) for phase in Phase)
