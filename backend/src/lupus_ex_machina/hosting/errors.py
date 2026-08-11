"""What hosting a game can refuse to do."""


class HostingError(RuntimeError):
    """Something the host would not do."""


class OneGameAtATimeError(HostingError):
    """A game is already being played, and V1 hosts one at a time (D-045, D-101)."""


class NoGameError(HostingError):
    """Something was asked of a game, and there is none."""


class NobodyIsPlayingError(HostingError):
    """Something only a person at the table can do was asked of a watched game.

    Refused rather than passed over: a button that answers and does nothing is
    the hardest kind of thing to diagnose from a screen.
    """


class AlreadyStartedError(HostingError):
    """A game was started twice. The second one would play the same table again."""
