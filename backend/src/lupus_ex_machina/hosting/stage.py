"""Where a hosted game is in its life (D-103).

Four stages rather than a pair of booleans: "created but not started" and
"abandoned" are real states a client has to be able to see, and a game that
answered `started=False, over=True` would be describing nothing.
"""

from enum import StrEnum


class Stage(StrEnum):
    """What is happening to a hosted game."""

    CREATED = "created"
    """Dealt and waiting. Nothing is played, and no model has been asked
    anything: creating and starting are two gestures (D-103)."""

    PLAYING = "playing"
    OVER = "over"
    """Played to a winner. It stays readable, and no longer holds the place."""

    ABANDONED = "abandoned"
    """Given up before its end. The place is free at once (D-101)."""
