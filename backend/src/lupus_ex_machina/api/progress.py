"""How far one client has got, and what that lets the game do (J8.4).

Two counts rather than one, and the difference between them is a defect this
project already paid for once: it froze a played game for ever.
"""

from lupus_ex_machina.hosting import HostedGame
from lupus_ex_machina.hosting.protocol import NOTHING_HEARD


class Progress:
    """What a client has been sent, in the two counts that matter.

    A client can only ever confirm a sequence **it has seen**, and a player sees
    a fraction of the journal: a wolf's night never reaches them, so they can
    never name it. The pacing, on the other hand, counts in facts *recorded*.
    Confirming one in terms of the other would stall a played game for ever —
    which is exactly what it did before this existed.

    So the server keeps both: how far down the journal it has read, and the last
    sequence it actually put on the wire. A client that names the second has
    caught up with the first.
    """

    def __init__(self) -> None:
        """Start with nothing read, nothing sent and nothing confirmed."""
        self.read = NOTHING_HEARD
        self.wired = NOTHING_HEARD
        self.confirmed = NOTHING_HEARD

    @property
    def caught_up(self) -> bool:
        """Whether the client has named everything that was put on the wire.

        Facts it was never entitled to see do not count against it: a night of
        the pack is nothing a villager can confirm, and holding a game until
        they did would hold it for ever.
        """
        return self.confirmed >= self.wired


def let_the_game_go_on(game: HostedGame, progress: Progress) -> None:
    """Tell the game how far this client has kept up, when it has.

    Called from both sides on purpose. A confirmation is the obvious one; the
    other is a fact the client was not entitled to, which leaves it up to date
    without it having said a word.
    """
    if progress.caught_up:
        game.hands.shown(progress.read)
