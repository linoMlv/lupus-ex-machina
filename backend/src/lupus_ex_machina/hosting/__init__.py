"""Hosting a game: its life, and the one place it is held (J8).

The engine plays a game and the API exposes one; this is what sits between. It
owns the two things neither of them should: when a game runs, and the fact that
there is only ever one of it (D-045, D-101).

Nothing here decides a rule. A hosted game deals its table from a configuration,
runs the engine as a task, and hands out the journal the engine wrote — which is
also the only description of the game anybody reads from (D-040).
"""

from lupus_ex_machina.hosting.errors import (
    AlreadyStartedError,
    HostingError,
    NoGameError,
    OneGameAtATimeError,
)
from lupus_ex_machina.hosting.game import HostedGame
from lupus_ex_machina.hosting.host import GameHost
from lupus_ex_machina.hosting.stage import Stage

__all__ = [
    "AlreadyStartedError",
    "GameHost",
    "HostedGame",
    "HostingError",
    "NoGameError",
    "OneGameAtATimeError",
    "Stage",
]
