"""Playing a game: the phases, and everything a running game accumulates.

A day is a series of auctions: the floor is won, never handed round the table
(D-002), and the round ends when the last player votes (D-013). A night is
silent, wakes every living player in turn, and settles nothing before the end
(D-006, D-083).

The package is laid out along that shape — :mod:`day`, :mod:`night`,
:mod:`closing` for the phases, :mod:`scribe` and :mod:`acting` for what asks an
agent and what applies its answer, :mod:`controls` for the two hands that reach
in from outside the rules. What follows is what the rest of the code needs to
play a game.
"""

from lupus_ex_machina.engine.runner.controls import DebateControl, FloorClaim
from lupus_ex_machina.engine.runner.game import (
    DEFAULT_MAX_ROUNDS,
    GameDidNotEndError,
    GameResult,
    play_game,
)

__all__ = [
    "DEFAULT_MAX_ROUNDS",
    "DebateControl",
    "FloorClaim",
    "GameDidNotEndError",
    "GameResult",
    "play_game",
]
