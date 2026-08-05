"""Playing a game from Night 0 to the end, and writing down what happened.

A day is a series of auctions: the floor is won, never handed round the table
(D-002), and the round ends when the last player votes (D-013). Those two rules
are what makes a debate a debate here — speaking costs the most in the auction
that follows, and voting buys the end of the round at the price of one's own
silence.

Every change the game goes through is recorded as a fact (D-040). Two habits
keep that honest: a phase is never entered except through :meth:`_Run.enter`,
which transitions and records in one move, and a ballot is never cast except
through :meth:`_Run._cast`. A caller that could do one without the other is a
caller that eventually does.

Two safety nets keep a game finite. Inside a day, a budget of turns at the floor
after which the remaining players are carried to a blank vote: waiting forever is
legal (D-048), so the round needs its own way out. Around the whole game, a
budget of rounds whose only purpose is to turn a hypothetical deadlock into a
loud failure instead of a hang.
"""

from collections.abc import Callable, Mapping
from typing import assert_never

from pydantic import BaseModel, ConfigDict

from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.bidding import Bid, elect
from lupus_ex_machina.engine.errors import EngineError, IllegalIntentError
from lupus_ex_machina.engine.events import (
    BallotAnnounced,
    BallotCast,
    BallotsRevealed,
    Event,
    EventPayload,
    FloorAuctioned,
    FloorClaimed,
    ForcedVoteReason,
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
    RevealedBallot,
    RoleAssigned,
    RoleRevealed,
    RunoffOpened,
    SeerFindingAnnounced,
    SeerInspected,
    ShotFired,
    SpeechDelivered,
    VoteForced,
    VoteResolved,
)
from lupus_ex_machina.engine.hunter import hunters_owing_a_shot, someone_to_take_along
from lupus_ex_machina.engine.intents import (
    Intent,
    RoleAction,
    SharePriority,
    TakeTurn,
    Wait,
)
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.night import (
    findings_of,
    night_callers,
    powers_spent_tonight,
    prey_drawn_by_lot,
    resolve_night,
    tied_prey,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.resolution import resolve_day, tied_targets
from lupus_ex_machina.engine.rng import Rng, create_rng
from lupus_ex_machina.engine.roles import RoleActionName, Team
from lupus_ex_machina.engine.state import GameState, count_words
from lupus_ex_machina.engine.validation import validate_intent
from lupus_ex_machina.engine.victory import Outcome, evaluate_victory
from lupus_ex_machina.engine.views import project

# Generous on purpose: with eight players, a real game lasts a handful of rounds.
DEFAULT_MAX_ROUNDS = 100

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


def _last_of_the_pack(callers: tuple[Player, ...]) -> PlayerId | None:
    """The last wolf the night calls, or ``None`` when it calls none.

    Where the pack's designation is closed. Read from the callers themselves
    rather than counted, so a pack of one, of two, or of none all work the same.
    """
    wolves = [caller for caller in callers if caller.team is Team.WEREWOLVES]
    return wolves[-1].id if wolves else None


def _round_progress(state: GameState) -> tuple[int, int]:
    """What a turn at the floor can add to a round: a word said, a ballot cast.

    Read off the state rather than off the intent that was played, so a refused
    intent counts as the nothing it was (D-060).
    """
    return len(state.floor), len(state.ballots)


class DebateControl:
    """The moderator's hand on how long a debate may run (D-048).

    Mutable, and consulted before every turn, because it is a control the user
    works during the game rather than a setting chosen before it: J11 wires the
    button to :meth:`cut_to`. Left alone, it never shortens anything.
    """

    def __init__(self, turns_left: int | None = None) -> None:
        """Take how many turns the debate may still have, or ``None`` for no limit."""
        self._turns_left = turns_left

    @property
    def turns_left(self) -> int | None:
        """Turns the debate may still have, ``None`` when the user has not said."""
        return self._turns_left

    def cut_to(self, turns: int) -> None:
        """Allow the debate that many more turns. Zero calls the vote at once."""
        self._turns_left = turns

    def spend_a_turn(self) -> None:
        """Count one turn against the allowance, if there is one."""
        if self._turns_left is not None:
            self._turns_left -= 1

    @property
    def is_out_of_turns(self) -> bool:
        """Whether the moderator has called time on the debate."""
        return self._turns_left is not None and self._turns_left <= 0


class FloorClaim:
    """The human player's claim on the next turn at the floor (D-014).

    Absolute priority, and it wins nothing: the claim is honoured instead of an
    auction rather than inside one. It is read *between* turns, which is the
    whole of "at the end of the turn under way, never inside it" — a turn is
    played to its end before the claim is looked at again.

    Spent once honoured, otherwise pressing the button would hand its owner the
    floor for the rest of the day. Mutable and read late, like DebateControl,
    because it is a button the user presses during the game (J11).
    """

    def __init__(self) -> None:
        """Start with nobody claiming anything."""
        self._claimed_by: PlayerId | None = None

    def claim(self, player: PlayerId) -> None:
        """Claim the next turn at the floor for that player."""
        self._claimed_by = player

    def take(self) -> PlayerId | None:
        """Hand back whoever claimed the floor, and forget the claim."""
        claimed, self._claimed_by = self._claimed_by, None
        return claimed


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
    control: DebateControl | None = None,
    claim: FloorClaim | None = None,
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
    run = _Run(
        agents,
        journal if journal is not None else Journal(),
        rng if rng is not None else create_rng(state.rules.table.seed),
        control=control if control is not None else DebateControl(),
        claim=claim if claim is not None else FloorClaim(),
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

    def __init__(
        self,
        agents: Agents,
        journal: Journal,
        rng: Rng,
        *,
        control: DebateControl | None = None,
        claim: FloorClaim | None = None,
    ) -> None:
        self._agents = agents
        self._journal = journal
        self._rng = rng
        self._control = control if control is not None else DebateControl()
        self._claim = claim if claim is not None else FloorClaim()
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
        """Run the debate, break a tie if there is one, then resolve the vote."""
        state = self._debate(state)

        tied = tied_targets(state)
        if tied:
            state = self._hold_a_silent_runoff(state, tied)

        self._read_the_count_out(state)
        return self._resolve(state, resolve_day, _vote_outcome)

    def _read_the_count_out(self, state: GameState) -> None:
        """Show the table who named whom, if the configuration allows it (D-013).

        Before the resolution rather than with it: the count is what the table
        reacts to, and what it leads to is the next fact along.
        """
        if not state.rules.information.reveal_ballots_at_the_count:
            return

        self._journal.record(
            BallotsRevealed(
                ballots=tuple(
                    RevealedBallot(voter=ballot.voter, target=ballot.target)
                    for ballot in state.ballots
                )
            ),
            at=state,
        )

    def _hold_a_silent_runoff(self, state: GameState, tied: tuple[PlayerId, ...]) -> GameState:
        """Put a tied vote back to the table, once, without a word (D-050, D-062).

        No auction and no debate: the question is closed, only the answer is
        reopened. Held once — a second tie spares everyone, which is where the
        rule stops rather than asking again forever.
        """
        state = state.reopened_for_runoff(tied)
        self._journal.record(RunoffOpened(targets=tied), at=state)

        for player in state.living:
            state = self._apply(state, player.id, self._ask(state, player.id))
        return self._carry_the_undecided_to_a_blank_vote(state)

    def _debate(self, state: GameState) -> GameState:
        """Auction the floor over and over until the round closes itself (D-013).

        The round ends when the last player votes, and nothing else ends it:
        that is the arbitrage the whole debate rests on — keep talking and leave
        the round open, or close it at the price of your own silence.

        The budget of turns is a safety net around that, not a rule of the game.
        It stops a table that never votes from spending an unbounded number of
        model calls (GL-7); the ways a debate is *meant* to end are in J5.5.
        """
        for _ in range(self._turn_budget(state)):
            if self._everyone_voted(state):
                return state
            if self._control.is_out_of_turns:
                return self._force_the_vote(state, ForcedVoteReason.MODERATOR)

            state, acted = self._auction_the_floor(state)
            self._control.spend_a_turn()
            if not acted:
                return self._force_the_vote(state, ForcedVoteReason.DEBATE_EXHAUSTED)

        return self._force_the_vote(state, ForcedVoteReason.TURN_BUDGET_SPENT)

    def _force_the_vote(self, state: GameState, reason: ForcedVoteReason) -> GameState:
        """Close a round the table did not close itself (D-048, D-060).

        Recorded before the ballots it produces: reading the journal, a blank
        vote from everyone at once means nothing without the line that says why
        it was called.
        """
        self._journal.record(VoteForced(reason=reason), at=state)
        return self._carry_the_undecided_to_a_blank_vote(state)

    @staticmethod
    def _turn_budget(state: GameState) -> int:
        """How many turns at the floor a single day may hold at the very most."""
        return state.rules.debate.turns_per_player_per_day * len(state.living)

    def _auction_the_floor(self, state: GameState) -> tuple[GameState, bool]:
        """Ask who wants to speak, and let the winner take their turn (D-002).

        Reports whether the turn *did* anything — a word or a ballot — which is
        how the caller tells a debate that is still going from one that has run
        out of things to say (D-060). Winning the floor and then waiting counts
        for nothing, and so does an intent the rules refused: what matters is
        whether the round moved, not whether somebody was asked.
        """
        speaker = self._claimed_floor(state) or self._won_floor(state)
        if speaker is None:
            return state, False

        before = _round_progress(state)
        state = self._apply(state, speaker, self._ask(state, speaker))
        return state, _round_progress(state) != before

    def _claimed_floor(self, state: GameState) -> PlayerId | None:
        """Whoever pressed the priority button, when they may still speak (D-014).

        A claim from a player the round has nothing left to offer — dead, or
        already voted — is dropped rather than held: it was made about a turn
        that no longer exists.
        """
        claimed = self._claim.take()
        if claimed is None or not project(state, claimed).may_speak:
            return None

        self._journal.record(FloorClaimed(player=claimed), at=state)
        return claimed

    def _won_floor(self, state: GameState) -> PlayerId | None:
        """Hold an auction and hand back whoever won it, if anyone did."""
        auction = elect(
            self._bids_of(state), floor=state.floor, rules=state.rules.debate, rng=self._rng
        )
        self._journal.record(FloorAuctioned(scores=auction.scores, winner=auction.winner), at=state)
        return auction.winner

    def _bids_of(self, state: GameState) -> dict[PlayerId, Bid]:
        """Ask everyone who still holds the floor how badly they want it.

        Whoever just spoke is not asked (D-002). The recency penalty would very
        likely have settled it anyway, but not asking is also one model call
        saved per turn, on the one call a game makes most often (GL-7).
        """
        just_spoke = state.floor[-1].speaker if state.floor else None
        return {
            player.id: self._agents[player.id].bid(project(state, player.id))
            for player in state.living
            if not state.has_voted(player.id) and player.id != just_spoke
        }

    def play_night(self, state: GameState) -> tuple[GameState, Outcome | None]:
        """Wake the roles in the order the night calls them, then resolve."""
        state = self.enter(state, Phase.NIGHT)
        state = self._collect_night_intents(state)

        self._hand_out_what_the_seers_read(state)
        self._write_down_what_was_used_up(state)
        return self._resolve(state, resolve_night, _night_outcome)

    def _write_down_what_was_used_up(self, state: GameState) -> None:
        """Record the potions this night emptied, before the round is wiped."""
        for actor, action in powers_spent_tonight(state):
            self._journal.record(PowerSpent(actor=actor, action=action), at=state)

    def _hand_out_what_the_seers_read(self, state: GameState) -> None:
        """Tell each seer what she read, and the table if she speaks (D-031)."""
        for finding in findings_of(state):
            self._journal.record(
                SeerInspected(
                    seer=finding.seer, target=finding.target, revelation=finding.revelation
                ),
                at=state,
            )
            if state.rules.roles.speaking_seer:
                self._journal.record(SeerFindingAnnounced(revelation=finding.revelation), at=state)

    def _collect_night_intents(self, state: GameState) -> GameState:
        """Ask everyone the night wakes, in the order their role is called (D-006).

        Reading the callers once is safe here, and only here: nothing kills
        anyone while the night runs, because everything it collects is settled
        at the end (D-006). The day has no such guarantee — the hunter fires as
        they die — which is why its own loop cannot take the same shortcut.
        """
        callers = night_callers(state)
        last_wolf = _last_of_the_pack(callers)

        for caller in callers:
            state = self._apply(state, caller.id, self._ask(state, caller.id))
            if caller.id == last_wolf:
                state = self._settle_what_the_pack_designates(state)
        return state

    def _settle_what_the_pack_designates(self, state: GameState) -> GameState:
        """Close the pack's designation as soon as its last wolf has answered.

        Inside the round of wake-ups rather than after it, because the roles
        woken later read the answer: the witch is shown the prey and may save
        them (D-029). Settled afterwards, a tie broken by the runoff — or a prey
        drawn by lot (D-081) — would kill someone she was never shown and could
        have saved. The wake order says she comes after the pack; this is what
        makes that mean *after it has finished*.
        """
        tied = tied_prey(state)
        if tied:
            state = self._hold_a_runoff(state, tied)
        return self._send_the_pack_to_the_lot(state)

    def _hold_a_runoff(self, state: GameState, tied: tuple[PlayerId, ...]) -> GameState:
        """Put the tied prey back to the pack, once, without a word (D-050, D-062)."""
        state = state.reopened_for_runoff(tied)
        self._journal.record(RunoffOpened(targets=tied), at=state)

        for wolf in night_callers(state):
            if wolf.team is Team.WEREWOLVES:
                state = self._apply(state, wolf.id, self._ask(state, wolf.id))
        return state

    def _send_the_pack_to_the_lot(self, state: GameState) -> GameState:
        """Draw a prey for a pack made to take one that still has not (D-081).

        Drawn here, once, and only after the runoff has had its chance — a pack
        settles its own tie before the lot ever settles it for them. The answer
        goes into the state so that the resolution *reads* it: a night asked
        twice cannot come back with two different victims.
        """
        drawn = prey_drawn_by_lot(state, rng=self._rng)
        return state if drawn is None else state.with_prey_drawn(drawn)

    def enter(self, state: GameState, phase: Phase, *, day: int | None = None) -> GameState:
        """Move to another phase and record it. The only way a phase is entered."""
        state = state.entering(phase, day=day)
        self._journal.record(PhaseEntered(phase=state.phase, day=state.day), at=state)
        return state

    # --- Steps -----------------------------------------------------------

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
        state = self._let_the_hunters_fire(state)

        outcome = evaluate_victory(state)
        if outcome is not None:
            state = self.enter(state, Phase.ENDED)
            self._journal.record(GameEnded(outcome=outcome), at=state)
            return state, outcome
        return state, None

    def _let_the_hunters_fire(self, state: GameState) -> GameState:
        """Fire every shot the round owes, before the victory is looked at (D-049).

        This is the one place a death happens in the middle of a phase, and the
        reason the whole thing is a loop: a hunter can take another hunter along.
        Each of them fires once, so it always ends.
        """
        while owed := hunters_owing_a_shot(state):
            hunter = owed[0]
            state = self.enter(state, Phase.AVENGING_SHOT)
            state = self._fire(state, hunter.id)
            state = self.enter(state, Phase.RESOLUTION)
        return state

    def _fire(self, state: GameState, hunter: PlayerId) -> GameState:
        """Take the hunter's aim, or the engine's when he will not give one."""
        aimed = self._aim_of(state, hunter)
        state = state.with_power_spent_by(hunter, RoleActionName.SHOOT)
        self._journal.record(PowerSpent(actor=hunter, action=RoleActionName.SHOOT), at=state)
        if aimed is None:
            return state

        target, chosen = aimed
        state = state.with_players_killed([target])
        self._journal.record(
            ShotFired(hunter=hunter, target=target, chosen_by_the_hunter=chosen), at=state
        )
        self._reveal_the_roles_of(state, (target,))
        return state

    def _aim_of(self, state: GameState, hunter: PlayerId) -> tuple[PlayerId, bool] | None:
        """Whom the shot takes, and whether the hunter is the one who said so."""
        intent = self._ask(state, hunter)
        if isinstance(intent, RoleAction) and self._accepts(state, hunter, intent):
            return intent.target, True

        self._refuse(state, hunter, intent)
        if not state.rules.roles.hunter_must_shoot:
            return None

        forced = someone_to_take_along(state, hunter)
        if forced is None:  # pragma: no cover - a game ends before a hunter is the last alive
            return None
        return forced, False

    def _accepts(self, state: GameState, actor: PlayerId, intent: Intent) -> bool:
        try:
            validate_intent(state, actor, intent)
        except IllegalIntentError:
            return False
        return True

    def _refuse(self, state: GameState, actor: PlayerId, intent: Intent) -> None:
        """Count and record an intent the rules would not take."""
        if isinstance(intent, Wait):
            return
        self._rejected += 1
        self._journal.record(
            IntentRejected(actor=actor, reason=f"{intent.kind} is not a shot"), at=state
        )

    def _reveal_the_roles_of(self, state: GameState, victims: tuple[PlayerId, ...]) -> None:
        """Announce what the deceased were, when the configuration allows it (D-072).

        Death itself was already recorded, and is never configurable.
        """
        if not state.rules.information.reveal_role_on_death:
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
            case TakeTurn():
                return self._play_turn(state, actor, intent)
            case SharePriority():
                state = state.with_priority_share_from(actor, intent.allocations)
                self._journal.record(
                    PriorityShared(actor=actor, allocations=intent.allocations), at=state
                )
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

    def _play_turn(self, state: GameState, actor: PlayerId, turn: TakeTurn) -> GameState:
        """Apply a turn: what was said first, then what was cast (D-051).

        The order is a rule of the game, not a detail of this method. A player
        may speak in the very turn they vote in but never after (D-028), and the
        table is told someone has voted only once they have had their say —
        otherwise the announcement would arrive before the words that explain it.
        """
        if (speech := turn.speech) is not None:
            state = self._say(state, actor, speech, turn)
        if turn.vote is not None:
            state = self._cast(state, actor, turn.vote.target)
        return state

    def _say(self, state: GameState, speaker: PlayerId, speech: str, turn: TakeTurn) -> GameState:
        """Record a turn at the floor, and remember the round had it.

        The journal keeps the words; the state keeps only what the next auction
        is scored against (D-002). The pack's own channel leaves no such trace:
        the night has no auction to score, and a round of it is short by design
        (D-007).
        """
        self._journal.record(self._speech_of(state, speaker, speech, turn), at=state)
        if state.phase is Phase.NIGHT:
            return state

        return state.with_speech_from(
            speaker,
            words=count_words(speech),
            addressed=turn.addressed,
            accused=turn.accused,
        )

    def _speech_of(
        self, state: GameState, speaker: PlayerId, speech: str, turn: TakeTurn
    ) -> EventPayload:
        """Route a line to the floor it was spoken on.

        The pack has its own channel at night (D-007), and what is said there is
        a fact with its own audience rather than public speech wearing a flag.
        """
        if state.phase is Phase.NIGHT:
            return PackSpeechDelivered(speaker=speaker, speech=speech)
        return SpeechDelivered(
            speaker=speaker, speech=speech, addressed=turn.addressed, accused=turn.accused
        )

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
