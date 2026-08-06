"""Agents that play without a language model.

They serve two purposes: they make a full game playable at no cost (GL-2), and
they are the fast, free regression suite of the rules. All but one lean on the
moves the view declares legal, so they never produce a refused intent.

The exception is :class:`RogueAgent`, which does nothing else. A game is only
half exercised by agents that behave: models will not, and the engine's refusals
are a normal path that deserves to be walked as often as the others.

Each of them also bids for the floor (D-002). The bids are blunt on purpose —
what a scripted agent is for is exercising the protocol, not playing well — but
they differ enough between agents that an auction has something to arbitrate.


None of them reflects at the close of a round (D-086): a scripted agent has no
thoughts to take stock with, and one that returned an empty one would still be
saying something. :class:`Scripted` gives them all the same silence.
"""

from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.intents import (
    Intent,
    IntentKind,
    PriorityPoint,
    RoleAction,
    SharePriority,
    TakeTurn,
    Vote,
    Wait,
)
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import Rng
from lupus_ex_machina.engine.roles import RoleActionName
from lupus_ex_machina.engine.turn import Reflection, Turn
from lupus_ex_machina.engine.views import PlayerView


class Scripted:
    """What every scripted agent shares: nothing to take stock with.

    A round closing teaches a model something (D-086); it teaches a table of
    rules nothing at all. Answering an empty reflection here rather than in each
    agent keeps the four of them about what they actually differ on.
    """

    async def reflect(self, view: PlayerView) -> Reflection:
        """Say nothing, which is what a scripted agent has to say."""
        return Reflection()


class SilentAgent(Scripted):
    """Never speaks, never names anyone: waits, and votes blank when it votes.

    Useful as a floor: a game where everyone stays silent must still terminate.
    """

    async def bid(self, view: PlayerView) -> Bid:
        """Want the floor as little as the scale allows."""
        return Bid(urgency=0, intention="Rien à dire.")

    async def decide(self, view: PlayerView) -> Turn:
        """Wait, unless a vote is possible — then vote blank."""
        return Turn(intent=self._move(view))

    @staticmethod
    def _move(view: PlayerView) -> Intent:
        if view.may_vote:
            return TakeTurn(vote=Vote())
        return Wait()


class AlwaysAccuseAgent(Scripted):
    """Always names the first player it may name.

    The mirror image of the silent agent: it closes rounds as fast as possible,
    which exercises eliminations and the end conditions.
    """

    async def bid(self, view: PlayerView) -> Bid:
        """Want the floor as much as the scale allows."""
        return Bid(urgency=100, intention="Accuser.")

    async def decide(self, view: PlayerView) -> Turn:
        """Put everything on the first prey, or vote against the first target."""
        return Turn(intent=self._move(view))

    @staticmethod
    def _move(view: PlayerView) -> Intent:
        if IntentKind.ROLE_ACTION in view.allowed_intents and view.action_targets:
            return RoleAction(action=view.available_actions[0], target=view.action_targets[0])
        if IntentKind.SHARE_PRIORITY in view.allowed_intents and view.action_targets:
            return SharePriority(
                allocations=(
                    PriorityPoint(target=view.action_targets[0], points=view.priority_budget),
                )
            )
        if view.may_vote:
            return TakeTurn(vote=Vote(target=view.vote_targets[0] if view.vote_targets else None))
        return Wait()


class RogueAgent(Scripted):
    """Always tries to devour someone, whatever the phase allows.

    Every intent it plays is refused outside the pack's turn, which is what
    makes it the only scripted way to exercise the engine's refusals — and the
    only way a test about them can be sure it is testing anything at all.
    """

    async def bid(self, view: PlayerView) -> Bid:
        """Bid like anyone else — what it does with the floor is the point."""
        return Bid(urgency=50, intention="Agir.")

    async def decide(self, view: PlayerView) -> Turn:
        """Play an intent the rules refuse: the pack never designates one by one."""
        prey = view.living_others[0] if view.living_others else view.self_id
        return Turn(intent=RoleAction(action=RoleActionName.DEVOUR, target=prey))


class RandomAgent(Scripted):
    """Picks uniformly among the legal moves, drawing from the injected generator.

    Every draw goes through that generator so a failing game can be replayed
    exactly from its seed.
    """

    def __init__(self, rng: Rng) -> None:
        """Take the generator every draw of this agent goes through."""
        self._rng = rng

    async def bid(self, view: PlayerView) -> Bid:
        """Want the floor to a degree drawn at random, like everything else."""
        return Bid(urgency=self._rng.randint(0, 100), intention="Peut-être parler.")

    async def decide(self, view: PlayerView) -> Turn:
        """Pick a legal move at random."""
        return Turn(intent=self._move(view))

    def _move(self, view: PlayerView) -> Intent:
        kind = self._rng.choice(view.allowed_intents)

        match kind:
            case IntentKind.TAKE_TURN:
                return self._take_a_turn(view)
            case IntentKind.SHARE_PRIORITY:
                return self._spread(view)
            case IntentKind.ROLE_ACTION:
                return RoleAction(
                    action=self._rng.choice(view.available_actions),
                    target=self._rng.choice(view.action_targets),
                )
            case _:
                return Wait()

    def _take_a_turn(self, view: PlayerView) -> Intent:
        """Do one of the three things a turn can be, drawn among those on offer.

        Speaking and voting are drawn apart rather than as three cases, so
        "speak and vote at once" comes up as often as the rules allow it (D-028)
        instead of being a case somebody remembered to write.

        Voting is what is left when the draw says not to speak: a turn is only
        ever offered by day, and by day the two halves open together. There is
        no longer a floor without a vote behind it — the night stopped offering
        one when it fell silent (D-083).
        """
        speaking = view.may_speak and self._rng.choice((True, False))
        voting = view.may_vote and (not speaking or self._rng.choice((True, False)))

        accused = self._accuses(view) if speaking else None
        return TakeTurn(
            speech=self._improvise(view, accused) if speaking else None,
            addressed=accused,
            accused=accused,
            vote=Vote(target=self._maybe_target(view)) if voting else None,
        )

    def _accuses(self, view: PlayerView) -> PlayerId | None:
        """Whom this line goes after, if anyone. Half the time, nobody."""
        others = view.living_others
        if not others or self._rng.choice((True, False)):
            return None
        return self._rng.choice(others)

    def _spread(self, view: PlayerView) -> Intent:
        """Put the whole budget on one prey drawn at random.

        A real spread is what a model will produce (D-008); a scripted agent
        only has to exercise the rule, and one lump keeps a game readable when
        it is printed.
        """
        return SharePriority(
            allocations=(
                PriorityPoint(
                    target=self._rng.choice(view.action_targets), points=view.priority_budget
                ),
            )
        )

    def _maybe_target(self, view: PlayerView) -> PlayerId | None:
        """Name someone, or vote blank — both are legal whenever voting is."""
        if not view.vote_targets:
            return None
        return self._rng.choice((*view.vote_targets, None))

    def _improvise(self, view: PlayerView, accused: PlayerId | None) -> str:
        """Produce a placeholder line. Real speech arrives with the models (J7).

        Players are named by their name, never by their identifier: a line goes
        to the shared transcript, which is read on screen and, from J7 on, by the
        models themselves.
        """
        if accused is None:
            return "Je réfléchis."
        return f"Je me méfie de {_name_of(view, accused)}."


def _name_of(view: PlayerView, player: PlayerId) -> str:
    """Public name of a player, as everyone at the table says it."""
    return next(other.name for other in view.players if other.id == player)
