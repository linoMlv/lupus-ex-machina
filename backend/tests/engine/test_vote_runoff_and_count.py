"""A tie put back to the table, and the count read out (J5.4, D-050, D-062).

The two moments a vote produces something the table reacts to: a second
round between the ex aequo, and who named whom (D-013, D-051, D-082).
"""

from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.events import (
    BallotsRevealed,
    Event,
    RunoffOpened,
    VoteResolved,
)
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import (
    GameRules,
    InformationOptions,
    VoteOptions,
)
from lupus_ex_machina.engine.runner import (
    DebateControl,
    FloorClaim,
)
from lupus_ex_machina.engine.runner.day import play_day
from lupus_ex_machina.engine.runner.scribe import Scribe
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.visibility import VisibilityScope
from support.agents import VotesFor
from support.games import (
    six_seats,
)

# --- A tied vote is put back to the table, once (J5.4, D-050, D-062) ---------


async def a_tied_day(
    targets: dict[int, PlayerId | None], *, rules: GameRules | None = None
) -> tuple[GameState, tuple[Event, ...]]:
    """Play a day where each seat votes for the player it was given."""
    state = create_game(six_seats(rules), rng=create_rng(12))
    agents: dict[PlayerId, Agent] = {
        player.id: VotesFor(targets.get(player.seat)) for player in state.players
    }
    journal = Journal()
    scribe = Scribe(agents, journal, create_rng(3))

    closed, _ = await play_day(
        scribe,
        scribe.enter(state, Phase.DAY, day=2),
        control=DebateControl(),
        claim=FloorClaim(),
    )
    return closed, journal.events


async def test_a_tied_vote_opens_a_runoff_between_the_players_it_tied_on() -> None:
    """Three against three: the table is asked again, and only about those two."""
    state = create_game(six_seats(), rng=create_rng(12))
    first, second = state.players[0].id, state.players[1].id

    _, events = await a_tied_day({0: second, 1: first, 2: first, 3: second, 4: first, 5: second})

    opened = [event.payload for event in events if isinstance(event.payload, RunoffOpened)]

    assert opened, "the tie was put back to the table"
    assert set(opened[0].targets) == {first, second}


async def test_a_runoff_is_held_once_and_spares_everyone_if_it_ties_again() -> None:
    """Second tie, nobody eliminated — the rule has a floor (D-050)."""
    state = create_game(six_seats(), rng=create_rng(12))
    first, second = state.players[0].id, state.players[1].id

    closed, events = await a_tied_day(
        {0: second, 1: first, 2: first, 3: second, 4: first, 5: second}
    )

    opened = [event.payload for event in events if isinstance(event.payload, RunoffOpened)]
    resolved = [event.payload for event in events if isinstance(event.payload, VoteResolved)]

    assert len(opened) == 1, "a runoff is held once, never twice"
    assert resolved[-1].eliminated is None
    assert len(closed.living) == 6


async def test_a_table_may_be_configured_to_let_a_tie_spare_everyone_at_once() -> None:
    """The runoff is a setting (D-050): without it, a tie is the final word."""
    state = create_game(six_seats(), rng=create_rng(12))
    first, second = state.players[0].id, state.players[1].id
    settled_at_once = GameRules(vote=VoteOptions(hold_a_runoff_on_a_tie=False))

    closed, events = await a_tied_day(
        {0: second, 1: first, 2: first, 3: second, 4: first, 5: second},
        rules=settled_at_once,
    )

    assert not [event for event in events if isinstance(event.payload, RunoffOpened)]
    assert len(closed.living) == 6, "and a tie still spares everyone"


async def test_a_vote_that_settles_needs_no_runoff() -> None:
    state = create_game(six_seats(), rng=create_rng(12))
    hunted = state.players[1].id

    closed, events = await a_tied_day(dict.fromkeys(range(6), hunted))

    assert not [event for event in events if isinstance(event.payload, RunoffOpened)]
    assert not closed.is_alive(hunted)


# --- The count, and what it lets the table see (J5.4.1, D-013, D-051) --------


async def a_settled_day(*, rules: GameRules | None = None) -> tuple[Event, ...]:
    """Play a day where the table names one player, under the given rules."""
    state = create_game(six_seats(rules), rng=create_rng(12))
    hunted = state.players[1].id
    agents: dict[PlayerId, Agent] = {player.id: VotesFor(hunted) for player in state.players}
    journal = Journal()
    scribe = Scribe(agents, journal, create_rng(3))

    await play_day(
        scribe,
        scribe.enter(state, Phase.DAY, day=2),
        control=DebateControl(),
        claim=FloorClaim(),
    )
    return journal.events


def counts_in(events: tuple[Event, ...]) -> list[BallotsRevealed]:
    return [event.payload for event in events if isinstance(event.payload, BallotsRevealed)]


async def test_the_count_shows_who_named_whom() -> None:
    """Revealed all at once, which is the answer to models voting in herds.

    It is also the moment the staging is built on (D-075): every head turns to
    its target at the same instant.
    """
    state = create_game(six_seats(), rng=create_rng(12))
    hunted = state.players[1].id

    counted = counts_in(await a_settled_day())

    assert counted, "the count is a fact of the game"
    named = {(ballot.voter, ballot.target) for ballot in counted[0].ballots}
    assert named == {(player.id, hunted) for player in state.players if player.id != hunted} | {
        (hunted, None)
    }, "every ballot, with whom it named"


async def test_a_game_may_keep_its_ballots_to_themselves() -> None:
    """Configurable, and the option decides whether the fact exists at all.

    An option that filtered the audience instead would leave the fact in the
    journal for anything that forgot to filter (D-009).
    """
    quiet = GameRules(information=InformationOptions(reveal_ballots_at_the_count=False))

    assert counts_in(await a_settled_day(rules=quiet)) == []


async def test_the_count_is_public() -> None:
    counted = counts_in(await a_settled_day())

    assert counted[0].audience.scope is VisibilityScope.PUBLIC
