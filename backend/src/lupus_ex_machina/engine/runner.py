"""Playing a game from Night 0 to the end.

The loop is deliberately plain here: everyone speaks in seat order, and a round
ends when everyone has voted (D-013). The bidding protocol that decides *who*
speaks is the heart of the project, and it belongs to J5 — putting a placeholder
for it now would only have to be undone.

Two safety nets keep a game finite. Inside a day, a budget of speaking rounds
after which the remaining players are carried to a blank vote: waiting forever is
legal (D-048), so the round needs its own way out. Around the whole game, a
budget of rounds whose only purpose is to turn a hypothetical deadlock into a
loud failure instead of a hang.
"""

from collections.abc import Mapping
from typing import assert_never

from pydantic import BaseModel, ConfigDict

from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.errors import EngineError, IllegalIntentError
from lupus_ex_machina.engine.intents import CastVote, Intent, RoleAction, Speak, Wait
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.resolution import resolve_day, resolve_night
from lupus_ex_machina.engine.roles import Team
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import validate_intent
from lupus_ex_machina.engine.victory import Outcome, evaluate_victory
from lupus_ex_machina.engine.views import project

# Generous on purpose: with eight players, a real game lasts a handful of rounds.
DEFAULT_MAX_ROUNDS = 100

# How many times every player may act in a day before the round is forced to a
# close. Enough for a debate, small enough to keep a stalled table cheap.
SPEAKING_ROUNDS_PER_DAY = 8

Agents = Mapping[PlayerId, Agent]


class GameDidNotEndError(EngineError, RuntimeError):
    """The round budget ran out — always an engine bug, never a game outcome."""


class GameResult(BaseModel):
    """Outcome of a finished game, with what it took to get there."""

    model_config = ConfigDict(frozen=True)

    state: GameState
    outcome: Outcome
    rounds: int
    rejected_intents: int = 0


def play_game(
    state: GameState,
    agents: Agents,
    *,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
) -> GameResult:
    """Play a full game and return who won."""
    run = _Run(agents)
    state = run.play_night_zero(state)

    for round_number in range(1, max_rounds + 1):
        state = state.entering(Phase.DAY, day=round_number)

        state, outcome = run.play_day(state)
        if outcome is not None:
            return run.result(state, outcome, round_number)

        state, outcome = run.play_night(state)
        if outcome is not None:
            return run.result(state, outcome, round_number)

    raise GameDidNotEndError(f"The game did not end within {max_rounds} rounds")


class _Run:
    """Bookkeeping of a single game: the agents, and what they got wrong."""

    def __init__(self, agents: Agents) -> None:
        self._agents = agents
        self._rejected = 0

    # --- Phases ----------------------------------------------------------

    def play_night_zero(self, state: GameState) -> GameState:
        """Let everyone take in the situation. No action is possible (D-032)."""
        for player in state.living:
            self._ask(state, player.id)
        return state

    def play_day(self, state: GameState) -> tuple[GameState, Outcome | None]:
        """Run the debate until everyone has voted, then resolve the vote."""
        for _ in range(SPEAKING_ROUNDS_PER_DAY):
            if self._everyone_voted(state):
                break
            state = self._collect_day_intents(state)
        else:
            state = self._carry_the_undecided_to_a_blank_vote(state)

        return self._resolve(state, resolve_day)

    def play_night(self, state: GameState) -> tuple[GameState, Outcome | None]:
        """Ask the pack for its prey, then resolve the night."""
        state = state.entering(Phase.NIGHT)
        for wolf in state.living_of_team(Team.WEREWOLVES):
            state = self._apply(state, wolf.id, self._ask(state, wolf.id))

        return self._resolve(state, resolve_night)

    # --- Steps -----------------------------------------------------------

    def _collect_day_intents(self, state: GameState) -> GameState:
        for player in state.living:
            if state.has_voted(player.id):
                continue
            state = self._apply(state, player.id, self._ask(state, player.id))
        return state

    def _carry_the_undecided_to_a_blank_vote(self, state: GameState) -> GameState:
        for player in state.living:
            if not state.has_voted(player.id):
                state = state.with_ballot_from(player.id)
        return state

    def _resolve(
        self,
        state: GameState,
        resolver: object,
    ) -> tuple[GameState, Outcome | None]:
        """Apply a resolution, then evaluate the victory — in that order (D-059)."""
        state = state.entering(Phase.RESOLUTION)
        state, _ = resolver(state)  # type: ignore[operator]

        outcome = evaluate_victory(state)
        if outcome is not None:
            return state.entering(Phase.ENDED), outcome
        return state, None

    # --- Agents ----------------------------------------------------------

    def _ask(self, state: GameState, player: PlayerId) -> Intent:
        return self._agents[player].decide(project(state, player))

    def _apply(self, state: GameState, actor: PlayerId, intent: Intent) -> GameState:
        """Validate then apply. An intent refused costs its author a turn, nothing more."""
        try:
            validate_intent(state, actor, intent)
        except IllegalIntentError:
            self._rejected += 1
            return state

        match intent:
            case CastVote():
                return state.with_ballot_from(actor, intent.target)
            case RoleAction():
                return state.with_night_choice_from(actor, intent.target)
            case Speak() | Wait():
                # Speech carries no state in J2: the transcript is born with the
                # event journal (J3), and the bidding that gives it weight in J5.
                return state
            case _:  # pragma: no cover - the union is closed, mypy proves this is dead
                assert_never(intent)

    # --- Result ----------------------------------------------------------

    @staticmethod
    def _everyone_voted(state: GameState) -> bool:
        return all(state.has_voted(player.id) for player in state.living)

    def result(self, state: GameState, outcome: Outcome, rounds: int) -> GameResult:
        """Build the result of a finished game."""
        return GameResult(
            state=state,
            outcome=outcome,
            rounds=rounds,
            rejected_intents=self._rejected,
        )
