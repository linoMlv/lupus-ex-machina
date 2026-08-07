"""Agents that think out loud into their notebook, and the games they play."""

from collections.abc import Sequence

from lupus_ex_machina.agents.scripted import AlwaysAccuseAgent, Scripted
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.events import (
    Event,
)
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameRules, NightOptions
from lupus_ex_machina.engine.runner import GameResult, play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.turn import (
    AddNote,
    Turn,
)
from lupus_ex_machina.engine.views import PlayerView

ANALYSIS = "Personne n'a rien dit d'utile pour l'instant."
NOTE = "Surveiller qui parle le moins."
FIRST_NOTE = "Adèle a parlé la première."
SECOND_NOTE = "Basile n'a rien dit."
REVISED_NOTE = "Adèle a parlé la première, et trop vite."

#: A pack made to leave every night with a victim, so a silent table still ends.
FORCED_DESIGNATION = GameRules(night=NightOptions(require_werewolf_target=True))


class ThinkingAgent(Scripted):
    """Plays like the accusing agent, but says what it was thinking first.

    The move itself is delegated rather than rewritten: what is under test is
    the thought travelling with it, and a second-hand copy of the accusing
    agent's rules would only be one more thing to keep in agreement.
    """

    def __init__(self) -> None:
        """Take the moves of a scripted agent, and think out loud on top."""
        self._moves = AlwaysAccuseAgent()

    async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
        """Bid like the agent whose moves it plays."""
        return await self._moves.bid(view, journal)

    async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
        """Hand back the same move, with an analysis and a note attached."""
        move = await self._moves.decide(view, journal)
        return move.model_copy(
            update={
                "reasoning": ANALYSIS,
                "notebook": (AddNote(note=NOTE),),
            }
        )


async def a_game_of_thinkers(seed: int = 3) -> GameResult:
    """One whole game where every seat thinks before it plays."""
    rng = create_rng(seed)
    state = create_game(GameRules(), rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: ThinkingAgent() for player in state.players}
    return await play_game(state, agents, rng=rng)
