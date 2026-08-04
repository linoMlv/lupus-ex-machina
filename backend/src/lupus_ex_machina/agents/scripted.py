"""Agents that play without a language model.

They serve two purposes: they make a full game playable at no cost (GL-2), and
they are the fast, free regression suite of the rules. All but one lean on the
moves the view declares legal, so they never produce a refused intent.

The exception is :class:`RogueAgent`, which does nothing else. A game is only
half exercised by agents that behave: models will not, and the engine's refusals
are a normal path that deserves to be walked as often as the others.
"""

from lupus_ex_machina.engine.intents import (
    CastVote,
    Intent,
    IntentKind,
    PriorityPoint,
    RoleAction,
    SharePriority,
    Speak,
    Wait,
)
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import Rng
from lupus_ex_machina.engine.roles import RoleActionName
from lupus_ex_machina.engine.views import PlayerView


class SilentAgent:
    """Never speaks, never names anyone: waits, and votes blank when it votes.

    Useful as a floor: a game where everyone stays silent must still terminate.
    """

    def decide(self, view: PlayerView) -> Intent:
        """Wait, unless a vote is possible — then vote blank."""
        if IntentKind.VOTE in view.allowed_intents:
            return CastVote()
        return Wait()


class AlwaysAccuseAgent:
    """Always names the first player it may name.

    The mirror image of the silent agent: it closes rounds as fast as possible,
    which exercises eliminations and the end conditions.
    """

    def decide(self, view: PlayerView) -> Intent:
        """Put everything on the first prey, or vote against the first target."""
        if IntentKind.SHARE_PRIORITY in view.allowed_intents and view.night_targets:
            return SharePriority(
                allocations=(
                    PriorityPoint(target=view.night_targets[0], points=view.priority_budget),
                )
            )
        if IntentKind.VOTE in view.allowed_intents:
            return CastVote(target=view.vote_targets[0] if view.vote_targets else None)
        return Wait()


class RogueAgent:
    """Always tries to devour someone, whatever the phase allows.

    Every intent it plays is refused outside the pack's turn, which is what
    makes it the only scripted way to exercise the engine's refusals — and the
    only way a test about them can be sure it is testing anything at all.
    """

    def decide(self, view: PlayerView) -> Intent:
        """Play an intent the rules refuse: the pack never designates one by one."""
        prey = view.living_others[0] if view.living_others else view.self_id
        return RoleAction(action=RoleActionName.DEVOUR, target=prey)


class RandomAgent:
    """Picks uniformly among the legal moves, drawing from the injected generator.

    Every draw goes through that generator so a failing game can be replayed
    exactly from its seed.
    """

    def __init__(self, rng: Rng) -> None:
        """Take the generator every draw of this agent goes through."""
        self._rng = rng

    def decide(self, view: PlayerView) -> Intent:
        """Pick a legal move at random."""
        kind = self._rng.choice(view.allowed_intents)

        match kind:
            case IntentKind.SPEAK:
                return Speak(speech=self._improvise(view))
            case IntentKind.VOTE:
                return CastVote(target=self._maybe_target(view))
            case IntentKind.SHARE_PRIORITY:
                return self._spread(view)
            case _:
                return Wait()

    def _spread(self, view: PlayerView) -> Intent:
        """Put the whole budget on one prey drawn at random.

        A real spread is what a model will produce (D-008); a scripted agent
        only has to exercise the rule, and one lump keeps a game readable when
        it is printed.
        """
        return SharePriority(
            allocations=(
                PriorityPoint(
                    target=self._rng.choice(view.night_targets), points=view.priority_budget
                ),
            )
        )

    def _maybe_target(self, view: PlayerView) -> PlayerId | None:
        """Name someone, or vote blank — both are legal whenever voting is."""
        if not view.vote_targets:
            return None
        return self._rng.choice((*view.vote_targets, None))

    def _improvise(self, view: PlayerView) -> str:
        """Produce a placeholder line. Real speech arrives with the models (J7).

        Players are named by their name, never by their identifier: a line goes
        to the shared transcript, which is read on screen and, from J7 on, by the
        models themselves.
        """
        others = view.living_others
        if not others:
            return "Je réfléchis."
        return f"Je me méfie de {_name_of(view, self._rng.choice(others))}."


def _name_of(view: PlayerView, player: PlayerId) -> str:
    """Public name of a player, as everyone at the table says it."""
    return next(other.name for other in view.players if other.id == player)
