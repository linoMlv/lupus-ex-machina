"""Playing a whole game.

These are the safety nets of the project: they catch deadlocks, unreachable
states and terminations that regress, for almost no runtime cost.
"""

import itertools

import pytest

from lupus_ex_machina.agents.scripted import (
    AlwaysAccuseAgent,
    RandomAgent,
    RogueAgent,
    SilentAgent,
)
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.bidding import Bid, DebateRules
from lupus_ex_machina.engine.composition import MAXIMUM_PLAYERS, MINIMUM_PLAYERS
from lupus_ex_machina.engine.events import (
    BallotAnnounced,
    BallotsRevealed,
    Event,
    EventKind,
    FloorAuctioned,
    ForcedVoteReason,
    RunoffOpened,
    SpeechDelivered,
    VoteForced,
    VoteResolved,
)
from lupus_ex_machina.engine.intents import (
    Intent,
    TakeTurn,
    Vote,
    Wait,
)
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.policy import InformationPolicy
from lupus_ex_machina.engine.rng import Rng, create_rng
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.runner import (
    DebateControl,
    FloorClaim,
    GameDidNotEndError,
    GameResult,
    _Run,
    play_game,
)
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.victory import Outcome, evaluate_victory
from lupus_ex_machina.engine.views import PlayerView
from lupus_ex_machina.engine.visibility import VisibilityScope

PLAYER_COUNTS = range(MINIMUM_PLAYERS, MAXIMUM_PLAYERS + 1)


def play(seed: int, *, player_count: int = 8) -> GameResult:
    """Play one full game of random agents, everything derived from one seed."""
    rng = create_rng(seed)
    state = create_game(player_count, rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: RandomAgent(rng=rng) for player in state.players}
    return play_game(state, agents)


def assert_properly_finished(result: GameResult) -> None:
    """Check a game really ended, rather than merely returning.

    ``result.outcome`` is typed as :class:`Outcome` and validated on
    construction, so asserting it *is* one proves nothing. What is worth
    checking is that the reported winner is the one the final state gives, and
    that the game was closed rather than abandoned mid-round.
    """
    assert result.state.phase is Phase.ENDED
    assert result.rounds >= 1
    assert evaluate_victory(result.state) is result.outcome


# --- A game runs to the end -------------------------------------------------


def test_a_full_game_reaches_a_winner() -> None:
    assert_properly_finished(play(seed=1))


@pytest.mark.parametrize("player_count", PLAYER_COUNTS)
def test_every_supported_table_size_can_be_played(player_count: int) -> None:
    assert_properly_finished(play(seed=2, player_count=player_count))


def test_a_hundred_games_of_different_seeds_all_terminate() -> None:
    """The regression net of J2.5.5: no seed may deadlock the engine."""
    results = [play(seed=seed) for seed in range(100)]

    for result in results:
        assert_properly_finished(result)
    assert len({result.outcome for result in results}) == 2, "both sides must be able to win"


def test_a_table_that_always_accuses_ends_quickly() -> None:
    """Eight players, an elimination most rounds: the game cannot drag on.

    The bound is what makes the name true — without it the round budget of 100
    would let a stalling regression through unnoticed.
    """
    state = create_game(8, rng=create_rng(4))
    agents: dict[PlayerId, Agent] = {player.id: AlwaysAccuseAgent() for player in state.players}

    result = play_game(state, agents)

    assert_properly_finished(result)
    assert result.rounds <= 8


def test_a_table_where_nobody_ever_dies_is_stopped_by_the_round_budget() -> None:
    """A degenerate table, and a real property of the rules.

    If every player votes blank and the pack designates nobody, no rule kills
    anyone, so the game genuinely never ends: a tie spares everyone (D-050) and
    the forced vote only closes the round, it does not eliminate. The round
    budget exists to turn that into a loud failure rather than a hang.
    """
    state = create_game(8, rng=create_rng(4))
    agents: dict[PlayerId, Agent] = {player.id: SilentAgent() for player in state.players}

    with pytest.raises(GameDidNotEndError):
        play_game(state, agents, max_rounds=10)


def test_the_same_table_ends_when_the_pack_is_made_to_designate_someone() -> None:
    """The way out of that deadlock the configuration offers (D-078, D-081).

    Same silent table, same seed: made to take someone every night, the pack
    eats the village and wins. Nothing else about the game changed.
    """
    rng = create_rng(4)
    state = create_game(8, rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: SilentAgent() for player in state.players}

    result = play_game(
        state,
        agents,
        max_rounds=10,
        policy=InformationPolicy(require_werewolf_target=True),
        rng=rng,
    )

    assert_properly_finished(result)
    assert result.outcome is Outcome.WEREWOLVES_WIN


def test_the_prey_the_lot_takes_depends_on_the_seed() -> None:
    """What D-081 bought: the same deadlock no longer kills the same players.

    A pack settled by seat took the lowest one every time, in every game.
    """
    victims = {_who_the_lot_took(seed) for seed in range(12)}

    assert len(victims) > 1


def _who_the_lot_took(seed: int) -> tuple[PlayerId, ...]:
    """Play the deadlocked table with one seed and report who the pack ate."""
    rng = create_rng(seed)
    state = create_game(8, rng=create_rng(4))
    agents: dict[PlayerId, Agent] = {player.id: SilentAgent() for player in state.players}

    result = play_game(
        state,
        agents,
        max_rounds=10,
        policy=InformationPolicy(require_werewolf_target=True),
        rng=rng,
    )
    return tuple(player.id for player in result.state.players if not player.alive)


# --- Determinism ------------------------------------------------------------


def game_of(result: GameResult) -> tuple[object, ...]:
    """Everything a seed is supposed to reproduce.

    The journal is compared fact by fact, envelope included, minus the one field
    a seed cannot govern: the timestamps come from the wall clock, and belong to
    the recording rather than to the game.
    """
    return (
        result.state,
        result.outcome,
        result.rounds,
        result.rejected_intents,
        tuple((event.sequence, event.phase, event.day, event.payload) for event in result.journal),
    )


def test_two_games_with_the_same_seed_are_identical() -> None:
    first, second = play(seed=7), play(seed=7)

    assert game_of(first) == game_of(second)


def test_different_seeds_produce_different_games() -> None:
    lengths = {play(seed=seed).rounds for seed in range(20)}

    assert len(lengths) > 1


# --- Victory is evaluated once the resolution is complete -------------------


def test_the_game_stops_as_soon_as_a_side_has_won() -> None:
    result = play(seed=3)

    assert evaluate_victory(result.state) is result.outcome


def test_a_finished_game_always_leaves_a_survivor() -> None:
    for seed in range(100):
        result = play(seed=seed)

        assert result.state.living, f"seed {seed} wiped out the whole table"


@pytest.mark.parametrize(
    ("wolves", "villagers"),
    [(w, v) for w, v in itertools.product(range(9), repeat=2) if 0 < w + v <= 2],
)
def test_no_game_with_two_survivors_or_fewer_is_still_running(wolves: int, villagers: int) -> None:
    """Why "everybody dies" is unreachable: such a game is already over (D-059).

    A night can only start from a running game, and no running game has two
    players or fewer, so no night can take the table from two to zero.
    """
    players = tuple(
        Player(
            id=PlayerId(f"p{seat}"),
            name=f"J{seat}",
            seat=seat,
            role=RoleName.WEREWOLF if seat < wolves else RoleName.VILLAGER,
        )
        for seat in range(wolves + villagers)
    )

    assert evaluate_victory(GameState.initial(players)) is not None


# --- Illegal intents --------------------------------------------------------


def test_an_agent_playing_illegal_intents_cannot_break_a_game() -> None:
    """The engine owns legality: a refused intent costs a turn, nothing else (D-001).

    One deranged player among sane ones — which is exactly what a misbehaving
    model will look like in J7.
    """
    rng = create_rng(9)
    state = create_game(8, rng=rng)
    agents: dict[PlayerId, Agent] = {
        player.id: RogueAgent() if player.seat == 0 else RandomAgent(rng=rng)
        for player in state.players
    }

    result = play_game(state, agents)

    assert_properly_finished(result)
    assert result.rejected_intents > 0


class TooEagerOnNightZeroAgent:
    """Takes the floor on Night 0, where nothing but waiting is legal. Sane after."""

    def __init__(self, rng: Rng) -> None:
        """Take the generator the sane half of this agent draws from."""
        self._sane = RandomAgent(rng=rng)

    def bid(self, view: PlayerView) -> Bid:
        """Bid flatly: what this agent is for is what it does with the floor."""
        return Bid(urgency=50, intention="Jouer.")

    def decide(self, view: PlayerView) -> Intent:
        """Speak out of turn on Night 0, then play normally."""
        if view.phase is Phase.NIGHT_ZERO:
            return TakeTurn(speech="Je prends la parole trop tôt.")
        return self._sane.decide(view)


def test_an_illegal_intent_on_night_zero_is_counted_as_refused() -> None:
    """Night 0 collects an intent from everyone, so it must judge them too (D-032).

    Dropping the illegal ones silently would leave `rejected_intents` — which the
    console command prints as "intentions refusées par le moteur" — quietly wrong
    about the one phase where every agent is asked and nothing is allowed.
    """
    rng = create_rng(13)
    state = create_game(6, rng=rng)
    agents: dict[PlayerId, Agent] = {
        player.id: TooEagerOnNightZeroAgent(rng) for player in state.players
    }

    result = play_game(state, agents)

    assert result.rejected_intents >= len(state.players)


class NeverVotesAgent:
    """Waits forever: legal (D-048), and a way to stall a round."""

    def bid(self, view: PlayerView) -> Bid:
        """Bid flatly: what this agent is for is what it does with the floor."""
        return Bid(urgency=50, intention="Jouer.")

    def decide(self, view: PlayerView) -> Intent:
        """Never do anything."""
        return Wait()


def test_a_player_who_never_votes_does_not_stall_the_round() -> None:
    """Waiting forever is legal, so the round needs its own way out (D-048, D-060)."""
    state = create_game(8, rng=create_rng(10))
    agents: dict[PlayerId, Agent] = {
        player.id: NeverVotesAgent() if player.seat == 0 else AlwaysAccuseAgent()
        for player in state.players
    }

    result = play_game(state, agents)

    assert_properly_finished(result)


def test_the_engine_refuses_to_loop_forever() -> None:
    """The round budget is a safety net, not a rule: exceeding it is a bug."""

    class ImmortalAgent:
        def bid(self, view: PlayerView) -> Bid:
            return Bid(urgency=50, intention="Voter.")

        def decide(self, view: PlayerView) -> Intent:
            return TakeTurn(vote=Vote())  # nobody ever dies

    state = create_game(6, rng=create_rng(11))
    agents: dict[PlayerId, Agent] = {player.id: ImmortalAgent() for player in state.players}

    with pytest.raises(RuntimeError, match="did not end"):
        play_game(state, agents, max_rounds=5)


# --- What each of the three turns actually does (J5.2.2) ---------------------


class TakesOneTurn:
    """Plays a turn written by the test on its first go, then waits for good."""

    def __init__(self, turn: TakeTurn) -> None:
        """Take the one turn this agent will play."""
        self._turn = turn
        self._played = False

    def bid(self, view: PlayerView) -> Bid:
        """Bid flatly: what this agent is for is what it does with the floor."""
        return Bid(urgency=50, intention="Jouer.")

    def decide(self, view: PlayerView) -> Intent:
        """Play the turn once, if the rules are offering it."""
        if self._played or not (view.may_speak or view.may_vote):
            return Wait()
        self._played = True
        return self._turn


def one_turn_of(turn: TakeTurn) -> tuple[GameState, PlayerId, tuple[Event, ...]]:
    """Play a single day up to its resolution, one seat playing that turn."""
    state = create_game(8, rng=create_rng(11)).entering(Phase.DAY, day=2)
    actor = state.living[0].id
    journal = Journal()
    run = _Run(
        {actor: TakesOneTurn(turn)}, journal, InformationPolicy(), DebateRules(), create_rng(1)
    )

    return run._apply(state, actor, turn), actor, journal.events


def kinds_of(events: tuple[Event, ...]) -> list[EventKind]:
    return [event.payload.kind for event in events]


def test_speaking_alone_leaves_the_round_open() -> None:
    after, actor, events = one_turn_of(TakeTurn(speech="Théo est bien silencieux."))

    assert EventKind.SPEECH_DELIVERED in kinds_of(events)
    assert not after.has_voted(actor), "the floor stays open"
    assert [speech.speaker for speech in after.floor] == [actor]


def test_voting_alone_closes_the_round_without_a_word() -> None:
    after, actor, events = one_turn_of(TakeTurn(vote=Vote()))

    assert EventKind.SPEECH_DELIVERED not in kinds_of(events)
    assert after.has_voted(actor)
    assert after.floor == (), "nothing was said, so the auction has nothing to weigh"


def test_speaking_and_voting_at_once_does_both_in_that_order() -> None:
    """Speech first, then the announcement (D-051).

    The other way round, the table would learn someone had voted before hearing
    the words that explain it.
    """
    after, actor, events = one_turn_of(
        TakeTurn(speech="J'ai assez entendu.", vote=Vote(target=None))
    )

    recorded = kinds_of(events)

    assert recorded.index(EventKind.SPEECH_DELIVERED) < recorded.index(EventKind.BALLOT_CAST)
    assert recorded.index(EventKind.BALLOT_CAST) < recorded.index(EventKind.BALLOT_ANNOUNCED)
    assert after.has_voted(actor)
    assert [speech.speaker for speech in after.floor] == [actor]


def test_a_turn_remembers_whom_it_addressed_and_accused() -> None:
    """What the next auction is scored against (D-002)."""
    state = create_game(8, rng=create_rng(11)).entering(Phase.DAY, day=2)
    speaker, target = state.living[0].id, state.living[1].id

    after, _, _ = one_turn_of(TakeTurn(speech="Théo, tu mens.", addressed=target, accused=target))

    assert after.floor[0].addressed == target
    assert after.floor[0].accused == target
    assert after.floor[0].speaker == speaker


# --- The floor is auctioned, not passed round the table (J5.3.3, D-002) ------


class Insistent:
    """Wants the floor as much as the scale allows, and says so at length."""

    def __init__(self, urgency: int) -> None:
        """Take how badly this seat wants to speak."""
        self._urgency = urgency

    def bid(self, view: PlayerView) -> Bid:
        """Always bid the same, so a test can reason about the order."""
        return Bid(urgency=self._urgency, intention="Parler.")

    def decide(self, view: PlayerView) -> Intent:
        """Speak while the floor is open, then vote blank to close the round."""
        if view.may_speak:
            return TakeTurn(speech="Je prends la parole.")
        return TakeTurn(vote=Vote()) if view.may_vote else Wait()


def a_day_of(
    urgencies: dict[int, int], claim: "FloorClaim | None" = None
) -> tuple[GameState, tuple[Event, ...]]:
    """Play one debate day where each seat bids the urgency it was given.

    The day alone rather than a whole game: what the auction does is the thing
    under test, and a game would drown it in nights and resolutions.
    """
    state = create_game(8, rng=create_rng(12))
    agents: dict[PlayerId, Agent] = {
        player.id: Insistent(urgencies[player.seat]) for player in state.players
    }
    journal = Journal()
    run = _Run(agents, journal, InformationPolicy(), DebateRules(), create_rng(3), claim=claim)

    run.play_day(run.enter(state, Phase.DAY, day=2))
    return state, journal.events


def auctions_in(events: tuple[Event, ...]) -> list[FloorAuctioned]:
    return [event.payload for event in events if isinstance(event.payload, FloorAuctioned)]


def speakers_of(events: tuple[Event, ...]) -> list[PlayerId]:
    return [event.payload.speaker for event in events if isinstance(event.payload, SpeechDelivered)]


def test_the_most_pressing_player_speaks_first_whatever_their_seat() -> None:
    """The whole point of the auction: the floor is won, not handed round.

    Seat 7 is last in every ordering the engine had before this; wanting it more
    than anyone else has to be enough to speak first.
    """
    state, events = a_day_of({seat: (100 if seat == 7 else 10) for seat in range(8)})

    assert speakers_of(events)[0] == state.players[7].id


def test_holding_the_floor_is_what_costs_the_most_in_the_next_auction() -> None:
    """The anti-monopoly of D-002: nobody speaks twice in a row while others want to."""
    _, events = a_day_of(dict.fromkeys(range(8), 50))

    spoken = speakers_of(events)

    assert len(spoken) > 1, "the day had a debate at all"
    assert all(first != second for first, second in itertools.pairwise(spoken))


def test_every_bid_is_written_down_including_the_losing_ones() -> None:
    """The raw material of the staging (D-075) and of tuning the coefficients."""
    _, events = a_day_of({seat: seat * 10 for seat in range(8)})

    auctions = auctions_in(events)

    assert auctions, "an auction is a fact of the game"
    assert len(auctions[0].scores) > 1, "the losers are kept too"


def test_an_auction_is_for_the_spectator_alone() -> None:
    """What a player wanted to say is not something the table gets to know."""
    _, events = a_day_of(dict.fromkeys(range(8), 50))

    auctions = auctions_in(events)

    assert auctions, "there were auctions to check in the first place"
    for auction in auctions:
        assert auction.audience.scope is VisibilityScope.SPECTATOR


# --- How a debate is meant to end (J5.5, D-048, D-060) -----------------------


def a_day_played_by(
    agents: dict[PlayerId, Agent],
    control: DebateControl | None = None,
    claim: "FloorClaim | None" = None,
) -> tuple[Event, ...]:
    """Play one debate day with the given agents, and hand back its journal."""
    state = create_game(8, rng=create_rng(12))
    journal = Journal()
    run = _Run(
        agents,
        journal,
        InformationPolicy(),
        DebateRules(),
        create_rng(3),
        control=control,
        claim=claim,
    )

    run.play_day(run.enter(state, Phase.DAY, day=2))
    return journal.events


def a_table_of(agent: type) -> dict[PlayerId, Agent]:
    return {player.id: agent() for player in create_game(8, rng=create_rng(12)).players}


def forced_votes_in(events: tuple[Event, ...]) -> list[VoteForced]:
    return [event.payload for event in events if isinstance(event.payload, VoteForced)]


def test_a_turn_nobody_used_means_the_debate_is_over() -> None:
    """An auction that produced neither a word nor a ballot ends the debate.

    D-060: a table with nothing left to say is put to the vote, rather than
    spending another round of model calls on the same silence.
    """
    events = a_day_played_by(a_table_of(NeverVotesAgent))

    forced = forced_votes_in(events)

    assert forced, "the vote was forced"
    assert forced[0].reason is ForcedVoteReason.DEBATE_EXHAUSTED


def test_a_debate_that_ran_out_of_turns_is_put_to_the_vote() -> None:
    """The budget of turns is the other way out, and it says so in the journal."""

    class TalksForever:
        def bid(self, view: PlayerView) -> Bid:
            return Bid(urgency=50, intention="Encore.")

        def decide(self, view: PlayerView) -> Intent:
            return TakeTurn(speech="Je continue.") if view.may_speak else Wait()

    events = a_day_played_by(a_table_of(TalksForever))

    forced = forced_votes_in(events)

    assert forced, "a debate that never votes is closed anyway"
    assert forced[0].reason is ForcedVoteReason.TURN_BUDGET_SPENT


def test_a_forced_vote_closes_the_round_for_everyone() -> None:
    """Whatever forced it, the round ends the way D-013 says it does."""
    events = a_day_played_by(a_table_of(NeverVotesAgent))

    voters = {event.payload.voter for event in events if isinstance(event.payload, BallotAnnounced)}

    assert len(voters) == 8, "every living player ends the round having voted"


def test_the_moderator_can_cut_a_debate_short() -> None:
    """D-048: the hand the user keeps on a debate that drags on.

    Set to zero, the vote is called at once — and the journal says it was the
    moderator, not the table running out of things to say.
    """
    events = a_day_played_by(a_table_of(NeverVotesAgent), control=DebateControl(turns_left=0))

    forced = forced_votes_in(events)

    assert forced[0].reason is ForcedVoteReason.MODERATOR
    assert not speakers_of(events), "nobody got to speak"


def test_the_moderator_leaves_the_debate_alone_by_default() -> None:
    assert DebateControl().turns_left is None


def test_a_moderator_who_allows_one_turn_gets_exactly_one() -> None:
    class TalksForever:
        def bid(self, view: PlayerView) -> Bid:
            return Bid(urgency=50, intention="Encore.")

        def decide(self, view: PlayerView) -> Intent:
            return TakeTurn(speech="Je continue.") if view.may_speak else Wait()

    events = a_day_played_by(a_table_of(TalksForever), control=DebateControl(turns_left=1))

    assert len(speakers_of(events)) == 1
    assert forced_votes_in(events)[0].reason is ForcedVoteReason.MODERATOR


def test_the_moderator_can_call_time_in_the_middle_of_a_debate() -> None:
    """What the control is for: a hand on a debate already under way (D-048).

    Set before the day, it is a setting. The point of D-048 is the user watching
    a debate drag on and stopping it, so the allowance is read again before
    every turn rather than once at the start.
    """
    control = DebateControl()

    class SpeaksThenCallsTime:
        """Speaks once, and cuts the debate short as it does — as the user would."""

        def bid(self, view: PlayerView) -> Bid:
            return Bid(urgency=50, intention="Encore.")

        def decide(self, view: PlayerView) -> Intent:
            if not view.may_speak:
                return Wait()
            control.cut_to(0)
            return TakeTurn(speech="Je serai bref.")

    events = a_day_played_by(a_table_of(SpeaksThenCallsTime), control=control)

    assert len(speakers_of(events)) == 1, "the debate stopped at the next turn"
    assert forced_votes_in(events)[0].reason is ForcedVoteReason.MODERATOR


# --- A tied vote is put back to the table, once (J5.4, D-050, D-062) ---------


class VotesFor:
    """Votes for whoever the test names, and never says a word."""

    def __init__(self, target: PlayerId | None) -> None:
        """Take the player this seat always names."""
        self._target = target

    def bid(self, view: PlayerView) -> Bid:
        """Bid low: this seat is here to vote, not to argue."""
        return Bid(urgency=10, intention="Voter.")

    def decide(self, view: PlayerView) -> Intent:
        """Name that player when the rules still offer them, otherwise vote blank."""
        if not view.may_vote:
            return Wait()
        wanted = self._target if self._target in view.vote_targets else None
        return TakeTurn(vote=Vote(target=wanted))


def a_tied_day(targets: dict[int, PlayerId | None]) -> tuple[GameState, tuple[Event, ...]]:
    """Play a day where each seat votes for the player it was given."""
    state = create_game(6, rng=create_rng(12))
    agents: dict[PlayerId, Agent] = {
        player.id: VotesFor(targets.get(player.seat)) for player in state.players
    }
    journal = Journal()
    run = _Run(agents, journal, InformationPolicy(), DebateRules(), create_rng(3))

    closed, _ = run.play_day(run.enter(state, Phase.DAY, day=2))
    return closed, journal.events


def test_a_tied_vote_opens_a_runoff_between_the_players_it_tied_on() -> None:
    """Three against three: the table is asked again, and only about those two."""
    state = create_game(6, rng=create_rng(12))
    first, second = state.players[0].id, state.players[1].id

    _, events = a_tied_day({0: second, 1: first, 2: first, 3: second, 4: first, 5: second})

    opened = [event.payload for event in events if isinstance(event.payload, RunoffOpened)]

    assert opened, "the tie was put back to the table"
    assert set(opened[0].targets) == {first, second}


def test_a_runoff_is_held_once_and_spares_everyone_if_it_ties_again() -> None:
    """Second tie, nobody eliminated — the rule has a floor (D-050)."""
    state = create_game(6, rng=create_rng(12))
    first, second = state.players[0].id, state.players[1].id

    closed, events = a_tied_day({0: second, 1: first, 2: first, 3: second, 4: first, 5: second})

    opened = [event.payload for event in events if isinstance(event.payload, RunoffOpened)]
    resolved = [event.payload for event in events if isinstance(event.payload, VoteResolved)]

    assert len(opened) == 1, "a runoff is held once, never twice"
    assert resolved[-1].eliminated is None
    assert len(closed.living) == 6


def test_a_vote_that_settles_needs_no_runoff() -> None:
    state = create_game(6, rng=create_rng(12))
    hunted = state.players[1].id

    closed, events = a_tied_day(dict.fromkeys(range(6), hunted))

    assert not [event for event in events if isinstance(event.payload, RunoffOpened)]
    assert not closed.is_alive(hunted)


# --- The count, and what it lets the table see (J5.4.1, D-013, D-051) --------


def a_settled_day(*, policy: InformationPolicy) -> tuple[Event, ...]:
    """Play a day where the table names one player, under the given policy."""
    state = create_game(6, rng=create_rng(12))
    hunted = state.players[1].id
    agents: dict[PlayerId, Agent] = {player.id: VotesFor(hunted) for player in state.players}
    journal = Journal()
    run = _Run(agents, journal, policy, DebateRules(), create_rng(3))

    run.play_day(run.enter(state, Phase.DAY, day=2))
    return journal.events


def counts_in(events: tuple[Event, ...]) -> list[BallotsRevealed]:
    return [event.payload for event in events if isinstance(event.payload, BallotsRevealed)]


def test_the_count_shows_who_named_whom() -> None:
    """Revealed all at once, which is the answer to models voting in herds.

    It is also the moment the staging is built on (D-075): every head turns to
    its target at the same instant.
    """
    state = create_game(6, rng=create_rng(12))
    hunted = state.players[1].id

    counted = counts_in(a_settled_day(policy=InformationPolicy()))

    assert counted, "the count is a fact of the game"
    named = {(ballot.voter, ballot.target) for ballot in counted[0].ballots}
    assert named == {(player.id, hunted) for player in state.players if player.id != hunted} | {
        (hunted, None)
    }, "every ballot, with whom it named"


def test_a_game_may_keep_its_ballots_to_themselves() -> None:
    """Configurable, and the option decides whether the fact exists at all.

    An option that filtered the audience instead would leave the fact in the
    journal for anything that forgot to filter (D-009).
    """
    quiet = InformationPolicy(reveal_ballots_at_the_count=False)

    assert counts_in(a_settled_day(policy=quiet)) == []


def test_the_count_is_public() -> None:
    counted = counts_in(a_settled_day(policy=InformationPolicy()))

    assert counted[0].audience.scope is VisibilityScope.PUBLIC


# --- The human player's two buttons (J5.6, D-014) ----------------------------


def test_asking_for_the_floor_the_ordinary_way_is_only_a_bid() -> None:
    """The human player's first button is a bid like any other (J5.6.1).

    The contrast with the second one is the whole of D-014: the same seat, with
    the same faint wish to speak, is passed over by the auction and served at
    once by the priority button. One asks, the other takes.
    """
    state = create_game(8, rng=create_rng(12))
    quiet = state.players[5].id
    urgencies = {seat: (0 if seat == 5 else 100) for seat in range(8)}

    _, asked = a_day_of(urgencies)

    claim = FloorClaim()
    claim.claim(quiet)
    _, took = a_day_of(urgencies, claim=claim)

    assert speakers_of(asked)[0] != quiet, "wanting it a little wins nothing"
    assert speakers_of(took)[0] == quiet, "the button owes the auction nothing"


def test_the_priority_button_takes_the_next_turn_whatever_the_bids() -> None:
    """D-014: absolute priority, and it does not need to win anything."""
    state = create_game(8, rng=create_rng(12))
    quiet = state.players[5].id
    claim = FloorClaim()
    claim.claim(quiet)

    _, events = a_day_of({seat: (0 if seat == 5 else 100) for seat in range(8)}, claim=claim)

    assert speakers_of(events)[0] == quiet


def test_the_priority_button_never_cuts_a_turn_in_half() -> None:
    """It applies at the end of the turn under way, never inside it (D-014)."""
    state = create_game(8, rng=create_rng(12))
    quiet = state.players[5].id
    claim = FloorClaim()

    class ClaimsWhileSpeaking:
        """Presses the button in the middle of somebody else's turn."""

        def bid(self, view: PlayerView) -> Bid:
            return Bid(urgency=100, intention="Parler.")

        def decide(self, view: PlayerView) -> Intent:
            claim.claim(quiet)
            return TakeTurn(speech="Je finis ma phrase.") if view.may_speak else Wait()

    agents: dict[PlayerId, Agent] = {
        player.id: (Insistent(0) if player.id == quiet else ClaimsWhileSpeaking())
        for player in state.players
    }
    events = a_day_played_by(agents, claim=claim)
    spoken = speakers_of(events)

    assert spoken[0] != quiet, "the turn under way was finished first"
    assert spoken[1] == quiet, "and the button was honoured at the next one"


def test_a_claim_is_spent_once_it_is_honoured() -> None:
    """Otherwise the button would hand its owner the floor for the rest of the day."""
    claim = FloorClaim()
    claim.claim(PlayerId("player-5"))

    assert claim.take() == PlayerId("player-5")
    assert claim.take() is None


def test_a_floor_nobody_claimed_is_nobody_s() -> None:
    assert FloorClaim().take() is None


def test_a_claim_from_someone_who_can_no_longer_speak_is_dropped() -> None:
    """A button pressed about a turn that no longer exists changes nothing.

    Voting gives up the floor for the round (D-013), so the claim of a player
    who has voted has nothing to claim. Honoured anyway, it would hand the turn
    to someone the rules then refuse, and the debate would read that refusal as
    a table with nothing left to say (D-060) and call the vote early.
    """
    state = create_game(8, rng=create_rng(12))
    voted = state.players[5].id
    claim = FloorClaim()

    agents: dict[PlayerId, Agent] = {
        player.id: (VotesFor(None) if player.id == voted else Insistent(50))
        for player in state.players
    }
    run = _Run(
        agents,
        journal := Journal(),
        InformationPolicy(),
        DebateRules(),
        create_rng(3),
        claim=claim,
    )
    opened = run.enter(state, Phase.DAY, day=2)

    # That seat votes, gives up the floor, and only then presses the button.
    opened = run._apply(opened, voted, TakeTurn(vote=Vote()))
    claim.claim(voted)
    run.play_day(opened)

    spoken = speakers_of(journal.events)

    assert voted not in spoken, "it had given up the floor"
    assert spoken, "and the debate carried on without it"
