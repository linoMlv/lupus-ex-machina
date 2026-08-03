"""Agents that play without a language model.

They serve two purposes: they make a full game playable at no cost (GL-2), and
they are the fast, free regression suite of the rules. Each one leans on the
moves the view declares legal, so none of them can produce a refused intent.
"""

from lupus_ex_machina.engine.intents import (
    CastVote,
    Intent,
    IntentKind,
    RoleAction,
    RoleActionName,
    Speak,
    Wait,
)
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import Rng
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
        """Devour, or vote against the first available target."""
        if IntentKind.ROLE_ACTION in view.allowed_intents and view.night_targets:
            return RoleAction(action=RoleActionName.DEVOUR, target=view.night_targets[0])
        if IntentKind.VOTE in view.allowed_intents:
            return CastVote(target=view.vote_targets[0] if view.vote_targets else None)
        return Wait()


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
            case IntentKind.ROLE_ACTION:
                return RoleAction(
                    action=RoleActionName.DEVOUR,
                    target=self._rng.choice(view.night_targets),
                )
            case _:
                return Wait()

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
