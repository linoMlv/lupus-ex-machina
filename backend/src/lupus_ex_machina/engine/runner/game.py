"""Playing a game from Night 0 to the end, and writing down what happened.

Every change the game goes through is recorded as a fact (D-040). Two habits
keep that honest: a phase is never entered except through :meth:`Scribe.enter`,
which transitions and records in one move, and a ballot is never cast except
through :func:`acting.cast`. A caller that could do one without the other is a
caller that eventually does.

Two safety nets keep a game finite. Inside a day, a budget of turns at the floor
after which the remaining players are carried to a blank vote: waiting forever is
legal (D-048), so the round needs its own way out. Around the whole game, a
budget of rounds whose only purpose is to turn a hypothetical deadlock into a
loud failure instead of a hang.
"""

from pydantic import BaseModel, ConfigDict

from lupus_ex_machina.engine.errors import EngineError
from lupus_ex_machina.engine.events import (
    Event,
    PackRevealed,
    PhaseEntered,
    PlayerSeated,
    RoleAssigned,
)
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.rng import Rng, create_rng
from lupus_ex_machina.engine.roles import Team
from lupus_ex_machina.engine.runner import acting
from lupus_ex_machina.engine.runner.controls import DebateControl, FloorClaim, Pacing
from lupus_ex_machina.engine.runner.day import play_day
from lupus_ex_machina.engine.runner.night import play_night
from lupus_ex_machina.engine.runner.scribe import Agents, Scribe
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.victory import Outcome

# Generous on purpose: with eight players, a real game lasts a handful of rounds.
DEFAULT_MAX_ROUNDS = 100


class GameDidNotEndError(EngineError, RuntimeError):
    """The round budget ran out — always an engine bug, never a game outcome."""


class GameResult(BaseModel):
    """Outcome of a finished game, with what it took to get there."""

    model_config = ConfigDict(frozen=True)

    state: GameState
    outcome: Outcome
    rounds: int
    rejected_intents: int = 0
    journal: tuple[Event, ...] = ()


async def play_game(
    state: GameState,
    agents: Agents,
    *,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    journal: Journal | None = None,
    control: DebateControl | None = None,
    claim: FloorClaim | None = None,
    pacing: Pacing | None = None,
    rng: Rng | None = None,
) -> GameResult:
    """Play a full game and return who won.

    A journal is opened for the game when the caller does not supply one, so
    playing never comes without a record of what happened.

    Pass the generator the game was dealt from to keep one seed behind
    everything it does (D-040). A game that does not supply one is dealt a fresh
    one from its own seed: the only draw a running game makes is the lot that
    settles a pack made to designate someone (D-081), and it has to be
    reproducible either way.

    How the game is played is not an argument: the rules travel in the state
    (D-068), so nothing here can be run under rules the view and the validator
    have not seen.
    """
    scribe = Scribe(
        agents,
        journal if journal is not None else Journal(),
        rng if rng is not None else create_rng(state.rules.table.seed),
    )
    moderator = (
        control if control is not None else DebateControl(state.rules.vote.turns_before_forced_vote)
    )
    button = claim if claim is not None else FloorClaim()
    pace = pacing if pacing is not None else Pacing()

    state = open_the_game(scribe, state)
    state = await play_night_zero(scribe, state, pace)

    for round_number in range(1, max_rounds + 1):
        state = scribe.enter(state, Phase.DAY, day=round_number)

        state, outcome = await play_day(scribe, state, control=moderator, claim=button, pacing=pace)
        if outcome is not None:
            return result(scribe, state, outcome, round_number)

        state, outcome = await play_night(scribe, state, pace)
        if outcome is not None:
            return result(scribe, state, outcome, round_number)

    raise GameDidNotEndError(f"The game did not end within {max_rounds} rounds")


def open_the_game(scribe: Scribe, state: GameState) -> GameState:
    """Seat the table, deal the roles, and let the pack meet (D-032).

    Seats first, roles after: everyone at the table is public, what each was
    dealt is not, so a filtered journal still opens on a whole table.
    """
    for player in state.players:
        scribe.record(PlayerSeated(player=player.id, name=player.name, seat=player.seat), at=state)
    for player in state.players:
        scribe.record(RoleAssigned(player=player.id, role=player.role), at=state)

    pack = tuple(player.id for player in state.players if player.team is Team.WEREWOLVES)
    scribe.record(PackRevealed(members=pack), at=state)
    scribe.record(PhaseEntered(phase=state.phase, day=state.day), at=state)
    return state


async def play_night_zero(scribe: Scribe, state: GameState, pacing: Pacing) -> GameState:
    """Let everyone take in the situation. No action is possible (D-032).

    Intents are judged here like anywhere else, even though nothing legal on
    Night 0 carries an effect: an agent that acts out of turn must be counted as
    refused rather than quietly ignored.
    """
    for player in state.living:
        await pacing.before_a_turn(recorded=len(scribe.events))
        state = await acting.take_turn(scribe, state, player.id)
    return state


def result(scribe: Scribe, state: GameState, outcome: Outcome, rounds: int) -> GameResult:
    """Build the result of a finished game."""
    return GameResult(
        state=state,
        outcome=outcome,
        rounds=rounds,
        rejected_intents=scribe.rejected,
        journal=scribe.events,
    )
