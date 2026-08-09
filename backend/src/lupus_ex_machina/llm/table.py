"""Seating a whole table of models, from the configuration (D-058, D-064, D-077).

One place where a seat becomes an agent, so the two things a seat is configured
with — its models and its temperament — are read once and nowhere else.

A seat nobody configured is dealt a temperament rather than left without one
(D-064): a table of sixteen identical voices is the failure mode the sixteen
temperaments exist to avoid. Dealt from the seed, so a game replays the same
table.
"""

from collections.abc import Mapping

from lupus_ex_machina.configuration.agents import AgentOptions
from lupus_ex_machina.configuration.system import SystemOptions
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.llm.agent import LlmAgent
from lupus_ex_machina.llm.completions import Completions
from lupus_ex_machina.llm.context import budget_for
from lupus_ex_machina.llm.personalities import drawn_personality, personalities


def seat_agents(
    state: GameState,
    options: AgentOptions,
    *,
    completions: Completions,
    seed: int,
    system: SystemOptions | None = None,
) -> Mapping[PlayerId, LlmAgent]:
    """One agent per seat, played the way that seat was configured."""
    settings = system if system is not None else SystemOptions()
    return {
        player.id: _seated(
            options, completions=completions, seat=player.seat, seed=seed, system=settings
        )
        for player in state.players
    }


def _seated(
    options: AgentOptions,
    *,
    completions: Completions,
    seat: int,
    seed: int,
    system: SystemOptions,
) -> LlmAgent:
    """The agent one seat is played by.

    The temperament of a seat left alone is drawn from the seed *and* the seat,
    so one table holds several of them — drawn from the seed alone, every seat
    would be dealt the same one.

    Its context budget comes from the window declared for the model it
    *generates* with (D-063): the auction runs on the other one and carries
    nothing but the moment, so it is the turn a window would ever be reached by.
    """
    profile = options.profile_of(seat)
    code = profile.personality or drawn_personality(seed + seat)
    return LlmAgent(
        completions=completions,
        personality=personalities()[code],
        bidding_model=profile.bidding_model,
        generation_model=profile.generation_model,
        temperature=profile.temperature,
        top_p=profile.top_p,
        budget=budget_for(profile.generation_model, system),
    )
