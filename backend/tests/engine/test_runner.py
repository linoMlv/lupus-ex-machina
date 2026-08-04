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
from lupus_ex_machina.engine.composition import MAXIMUM_PLAYERS, MINIMUM_PLAYERS
from lupus_ex_machina.engine.events import Event, EventKind
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
    GameDidNotEndError,
    GameResult,
    _Run,
    play_game,
)
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.victory import Outcome, evaluate_victory
from lupus_ex_machina.engine.views import PlayerView

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
    run = _Run({actor: TakesOneTurn(turn)}, journal, InformationPolicy(), create_rng(1))

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
