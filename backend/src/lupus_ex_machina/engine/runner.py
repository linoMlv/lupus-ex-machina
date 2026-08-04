"""Playing a game from Night 0 to the end, and writing down what happened.

The loop is deliberately plain here: everyone speaks in seat order, and a round
ends when everyone has voted (D-013). The bidding protocol that decides *who*
speaks is the heart of the project, and it belongs to J5 — putting a placeholder
for it now would only have to be undone.

Every change the game goes through is recorded as a fact (D-040). Two habits
keep that honest: a phase is never entered except through :meth:`_Run.enter`,
which transitions and records in one move, and a ballot is never cast except
through :meth:`_Run._cast`. A caller that could do one without the other is a
caller that eventually does.

Two safety nets keep a game finite. Inside a day, a budget of speaking rounds
after which the remaining players are carried to a blank vote: waiting forever is
legal (D-048), so the round needs its own way out. Around the whole game, a
budget of rounds whose only purpose is to turn a hypothetical deadlock into a
loud failure instead of a hang.
"""

from collections.abc import Callable, Mapping
from typing import assert_never

from pydantic import BaseModel, ConfigDict

from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.errors import EngineError, IllegalIntentError
from lupus_ex_machina.engine.events import (
    BallotAnnounced,
    BallotCast,
    Event,
    EventPayload,
    GameEnded,
    IntentRejected,
    NightPowerUsed,
    NightResolved,
    PackRevealed,
    PackSpeechDelivered,
    PhaseEntered,
    PlayerSeated,
    PowerSpent,
    PriorityShared,
    RoleAssigned,
    RoleRevealed,
    RunoffOpened,
    SeerFindingAnnounced,
    SeerInspected,
    SpeechDelivered,
    VoteResolved,
)
from lupus_ex_machina.engine.intents import (
    CastVote,
    Intent,
    RoleAction,
    SharePriority,
    Speak,
    Wait,
)
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.night import (
    findings_of,
    night_callers,
    powers_spent_tonight,
    resolve_night,
    tied_prey,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.policy import InformationPolicy
from lupus_ex_machina.engine.resolution import resolve_day
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

# What `resolve_day` and `resolve_night` both are: they close a phase, returning
# the new state and whoever died, if anyone.
Resolver = Callable[[GameState], tuple[GameState, tuple[PlayerId, ...]]]

# How a closed phase announces its outcome. Both resolutions produce the same
# shape — a victim or nobody — but they are two different facts of the game.
Announcement = Callable[[tuple[PlayerId, ...]], EventPayload]


def _vote_outcome(victims: tuple[PlayerId, ...]) -> EventPayload:
    return VoteResolved(eliminated=victims[0] if victims else None)


def _night_outcome(victims: tuple[PlayerId, ...]) -> EventPayload:
    return NightResolved(victims=victims)


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


def play_game(
    state: GameState,
    agents: Agents,
    *,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    journal: Journal | None = None,
    policy: InformationPolicy | None = None,
) -> GameResult:
    """Play a full game and return who won.

    A journal is opened for the game when the caller does not supply one, so
    playing never comes without a record of what happened.
    """
    run = _Run(
        agents,
        journal if journal is not None else Journal(),
        policy if policy is not None else InformationPolicy(),
    )
    state = run.open_the_game(state)
    state = run.play_night_zero(state)

    for round_number in range(1, max_rounds + 1):
        state = run.enter(state, Phase.DAY, day=round_number)

        state, outcome = run.play_day(state)
        if outcome is not None:
            return run.result(state, outcome, round_number)

        state, outcome = run.play_night(state)
        if outcome is not None:
            return run.result(state, outcome, round_number)

    raise GameDidNotEndError(f"The game did not end within {max_rounds} rounds")


class _Run:
    """Bookkeeping of a single game: the agents, the journal, and what went wrong."""

    def __init__(self, agents: Agents, journal: Journal, policy: InformationPolicy) -> None:
        self._agents = agents
        self._journal = journal
        self._policy = policy
        self._rejected = 0

    # --- Phases ----------------------------------------------------------

    def open_the_game(self, state: GameState) -> GameState:
        """Seat the table, deal the roles, and let the pack meet (D-032).

        Seats first, roles after: everyone at the table is public, what each was
        dealt is not, so a filtered journal still opens on a whole table.
        """
        for player in state.players:
            self._journal.record(
                PlayerSeated(player=player.id, name=player.name, seat=player.seat), at=state
            )
        for player in state.players:
            self._journal.record(RoleAssigned(player=player.id, role=player.role), at=state)

        pack = tuple(player.id for player in state.players if player.team is Team.WEREWOLVES)
        self._journal.record(PackRevealed(members=pack), at=state)
        self._journal.record(PhaseEntered(phase=state.phase, day=state.day), at=state)
        return state

    def play_night_zero(self, state: GameState) -> GameState:
        """Let everyone take in the situation. No action is possible (D-032).

        Intents are judged here like anywhere else, even though nothing legal on
        Night 0 carries an effect: an agent that acts out of turn must be counted
        as refused rather than quietly ignored.
        """
        for player in state.living:
            state = self._apply(state, player.id, self._ask(state, player.id))
        return state

    def play_day(self, state: GameState) -> tuple[GameState, Outcome | None]:
        """Run the debate until everyone has voted, then resolve the vote."""
        for _ in range(SPEAKING_ROUNDS_PER_DAY):
            if self._everyone_voted(state):
                break
            state = self._collect_day_intents(state)
        else:
            state = self._carry_the_undecided_to_a_blank_vote(state)

        return self._resolve(state, resolve_day, _vote_outcome)

    def play_night(self, state: GameState) -> tuple[GameState, Outcome | None]:
        """Wake the roles in order, hold a runoff if the pack tied, then resolve."""
        state = self.enter(state, Phase.NIGHT)
        state = self._collect_night_intents(state)

        tied = tied_prey(state)
        if tied:
            state = self._hold_a_runoff(state, tied)

        self._hand_out_what_the_seers_read(state)
        self._write_down_what_was_used_up(state)
        return self._resolve(state, self._resolve_the_night, _night_outcome)

    def _write_down_what_was_used_up(self, state: GameState) -> None:
        """Record the potions this night emptied, before the round is wiped."""
        for actor, action in powers_spent_tonight(state):
            self._journal.record(PowerSpent(actor=actor, action=action), at=state)

    def _hand_out_what_the_seers_read(self, state: GameState) -> None:
        """Tell each seer what she read, and the table if she speaks (D-031)."""
        for finding in findings_of(state, policy=self._policy):
            self._journal.record(
                SeerInspected(
                    seer=finding.seer, target=finding.target, revelation=finding.revelation
                ),
                at=state,
            )
            if self._policy.speaking_seer:
                self._journal.record(SeerFindingAnnounced(revelation=finding.revelation), at=state)

    def _collect_night_intents(self, state: GameState) -> GameState:
        """Ask everyone the night wakes, in the order their role is called (D-006).

        Reading the callers once is safe here, and only here: nothing kills
        anyone while the night runs, because everything it collects is settled
        at the end (D-006). The day has no such guarantee — the hunter fires as
        they die — which is why its own loop cannot take the same shortcut.
        """
        for caller in night_callers(state, policy=self._policy):
            state = self._apply(state, caller.id, self._ask(state, caller.id))
        return state

    def _hold_a_runoff(self, state: GameState, tied: tuple[PlayerId, ...]) -> GameState:
        """Put the tied prey back to the pack, once, without a word (D-050, D-062)."""
        state = state.reopened_for_runoff(tied)
        self._journal.record(RunoffOpened(targets=tied), at=state)

        for wolf in night_callers(state, policy=self._policy):
            if wolf.team is Team.WEREWOLVES:
                state = self._apply(state, wolf.id, self._ask(state, wolf.id))
        return state

    def _resolve_the_night(self, state: GameState) -> tuple[GameState, tuple[PlayerId, ...]]:
        """Close the night with the options the game was configured with."""
        return resolve_night(state, policy=self._policy)

    def enter(self, state: GameState, phase: Phase, *, day: int | None = None) -> GameState:
        """Move to another phase and record it. The only way a phase is entered."""
        state = state.entering(phase, day=day)
        self._journal.record(PhaseEntered(phase=state.phase, day=state.day), at=state)
        return state

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
                state = self._cast(state, player.id)
        return state

    def _resolve(
        self,
        state: GameState,
        resolver: Resolver,
        announce: Announcement,
    ) -> tuple[GameState, Outcome | None]:
        """Apply a resolution, then evaluate the victory — in that order (D-059)."""
        state = self.enter(state, Phase.RESOLUTION)
        state, victims = resolver(state)
        self._journal.record(announce(victims), at=state)
        self._reveal_the_roles_of(state, victims)

        outcome = evaluate_victory(state)
        if outcome is not None:
            state = self.enter(state, Phase.ENDED)
            self._journal.record(GameEnded(outcome=outcome), at=state)
            return state, outcome
        return state, None

    def _reveal_the_roles_of(self, state: GameState, victims: tuple[PlayerId, ...]) -> None:
        """Announce what the deceased were, when the configuration allows it (D-072).

        Death itself was already recorded, and is never configurable.
        """
        if not self._policy.reveal_role_on_death:
            return
        for victim in victims:
            self._journal.record(
                RoleRevealed(player=victim, role=state.player(victim).role), at=state
            )

    # --- Agents ----------------------------------------------------------

    def _ask(self, state: GameState, player: PlayerId) -> Intent:
        return self._agents[player].decide(project(state, player))

    def _apply(self, state: GameState, actor: PlayerId, intent: Intent) -> GameState:
        """Validate then apply. An intent refused costs its author a turn, nothing more."""
        try:
            validate_intent(state, actor, intent)
        except IllegalIntentError as refusal:
            self._rejected += 1
            self._journal.record(IntentRejected(actor=actor, reason=str(refusal)), at=state)
            return state

        match intent:
            case CastVote():
                return self._cast(state, actor, intent.target)
            case SharePriority():
                state = state.with_priority_share_from(actor, intent.allocations)
                self._journal.record(
                    PriorityShared(actor=actor, allocations=intent.allocations), at=state
                )
                return state
            case Speak():
                self._journal.record(self._speech_of(state, actor, intent.speech), at=state)
                return state
            case RoleAction():
                state = state.with_night_choice_from(actor, intent.action, intent.target)
                self._journal.record(
                    NightPowerUsed(actor=actor, action=intent.action, target=intent.target),
                    at=state,
                )
                return state
            case Wait():
                # Silence leaves the state untouched, and says nothing anyone
                # could act on while the floor still goes round the table. It
                # becomes a fact worth recording when the bidding does (J5).
                return state
            case _:  # pragma: no cover - the union is closed, mypy proves this is dead
                assert_never(intent)

    def _speech_of(self, state: GameState, speaker: PlayerId, speech: str) -> EventPayload:
        """Route a line to the floor it was spoken on.

        The pack has its own channel at night (D-007), and what is said there is
        a fact with its own audience rather than public speech wearing a flag.
        """
        if state.phase is Phase.NIGHT:
            return PackSpeechDelivered(speaker=speaker, speech=speech)
        return SpeechDelivered(speaker=speaker, speech=speech)

    def _cast(self, state: GameState, voter: PlayerId, target: PlayerId | None = None) -> GameState:
        """Record a vote. The only way a ballot enters the game.

        Two facts, because the rules address two audiences: *that* someone voted
        closes the round and is public (D-051), *whom* they named stays theirs
        until the count — unless the ballot is blank, which is public at once
        (D-027). The audience of each is settled by the fact itself.
        """
        state = state.with_ballot_from(voter, target)
        self._journal.record(BallotCast(voter=voter, target=target), at=state)
        self._journal.record(BallotAnnounced(voter=voter), at=state)
        return state

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
            journal=self._journal.events,
        )
