"""Etanchéité, proven rather than intended (GL-3).

These are the tests the jalon exists for. They are written as general properties
swept over the hundred scripted games of J2.5.5, never as scenarios: the case
somebody thinks of is not the case that leaks, and a suite of examples is
blindest exactly where its author was.

Two of them look for a value *anywhere* in a projection, whatever field it sits
under and however deeply it is nested. A leak rarely arrives under a field named
after the secret; it arrives as a count, a length, or a well-meant convenience.
"""

from collections.abc import Iterable, Iterator

import pytest

from lupus_ex_machina.agents.scripted import RandomAgent, RogueAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.events import (
    BallotCast,
    Event,
    IntentRejected,
    NightResolved,
    NotebookEntryRecorded,
    PackRevealed,
    PhaseEntered,
    PriorityShared,
    PrivateReasoningRecorded,
    RoleRevealed,
    VoteResolved,
)
from lupus_ex_machina.engine.journal import Journal, project_journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.replay import replay
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.roles import RoleName, Team
from lupus_ex_machina.engine.rules import GameRules, InformationOptions, RoleOptions
from lupus_ex_machina.engine.runner import GameResult, play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.views import project
from lupus_ex_machina.engine.visibility import SPECTATOR, Recipient

#: Wide enough that every rule of the game gets exercised, small enough to stay
#: a second of test time.
CORPUS = range(100)

#: A handful of games for the properties that inspect every value of every
#: projection, which costs more than counting events.
SAMPLE = range(12)


def played(seed: int, *, rules: GameRules | None = None) -> GameResult:
    """Play one full game of random agents, journalling everything."""
    rng = create_rng(seed)
    state = create_game(rules, rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: RandomAgent(rng=rng) for player in state.players}
    return play_game(state, agents, journal=Journal())


def played_with_a_rogue(seed: int) -> GameResult:
    """A game where one seat keeps playing intents the rules refuse.

    The well-behaved agents never produce one, so without this the property
    below would hold over an empty set and prove nothing.
    """
    rng = create_rng(seed)
    state = create_game(rng=rng)
    agents: dict[PlayerId, Agent] = {
        player.id: RogueAgent() if player.seat == 0 else RandomAgent(rng=rng)
        for player in state.players
    }
    return play_game(state, agents, journal=Journal())


def everyone_at(state: GameState) -> list[Recipient]:
    """Every recipient a projection can be built for, the spectator included."""
    return [Recipient.of(player) for player in state.players] + [SPECTATOR]


def scalars_in(value: object) -> Iterator[object]:
    """Every leaf of a serialised structure, however deeply it is nested.

    This is what makes "in no form at all" testable: a secret that surfaced as a
    count, a list length or a stray field is a leaf like any other.
    """
    match value:
        case dict():
            for nested in value.values():
                yield from scalars_in(nested)
        case list() | tuple():
            for nested in value:
                yield from scalars_in(nested)
        case _:
            yield value


def leaves_of(events: Iterable[Event]) -> set[object]:
    """Every value a recipient could read off their projection."""
    return {leaf for event in events for leaf in scalars_in(event.model_dump(mode="json"))}


def payloads_of(events: Iterable[Event], kind: type) -> list[Event]:
    return [event for event in events if isinstance(event.payload, kind)]


# --- J3.2.1 — no fact of a higher visibility reaches a projection ------------


@pytest.mark.parametrize("seed", CORPUS)
def test_a_projection_only_ever_holds_facts_its_recipient_is_entitled_to(seed: int) -> None:
    result = played(seed)

    for recipient in everyone_at(result.state):
        for event in project_journal(result.journal, recipient):
            assert event.is_visible_to(recipient), f"{event.payload.kind} reached {recipient}"


def test_the_corpus_actually_hides_things_from_everyone() -> None:
    """Guard the guard: over a game where nothing is secret, every test above passes."""
    result = played(seed=1)

    for recipient in everyone_at(result.state):
        withheld = len(result.journal) - len(project_journal(result.journal, recipient))
        if recipient.is_spectator:
            assert withheld == 0, "the spectator is omniscient"
        else:
            assert withheld > 0, f"nothing was ever hidden from {recipient}"


@pytest.mark.parametrize("seed", SAMPLE)
def test_no_player_can_read_a_role_other_than_their_own(seed: int) -> None:
    """The one secret the whole game turns on, searched for under any field.

    Run with every setting that hands a role out switched off — no revelation at
    death, and a seer who only reads "wolf or not". Any role name a player can
    read is then necessarily a leak, which is what makes the sweep worth running.
    What the seer is *entitled* to read is a rule of her own, tested with her.
    """
    result = played(
        seed,
        rules=GameRules(
            information=InformationOptions(reveal_role_on_death=False),
            roles=RoleOptions(seer_learns_exact_role=False),
        ),
    )

    for player in result.state.players:
        readable = leaves_of(project_journal(result.journal, Recipient.of(player)))
        foreign = {role.value for role in RoleName} - {player.role.value}

        assert not (readable & foreign), f"{player.name} could read {readable & foreign}"


@pytest.mark.parametrize("seed", SAMPLE)
def test_nobody_learns_whom_another_player_voted_for(seed: int) -> None:
    """Who voted is the pressure of the round; for whom is not (D-013)."""
    result = played(seed)

    for player in result.state.players:
        readable = payloads_of(project_journal(result.journal, Recipient.of(player)), BallotCast)

        for event in readable:
            ballot = event.payload
            assert isinstance(ballot, BallotCast)
            assert ballot.voter == player.id or ballot.target is None, (
                "only one's own ballots, and the blank ones everybody sees (D-027)"
            )


@pytest.mark.parametrize("seed", SAMPLE)
def test_a_voter_can_always_re_read_their_own_ballot(seed: int) -> None:
    """The counterpart of the rule above, and what an agent needs in J7.

    A player keeps analysing after voting (D-028), so their own vote has to stay
    part of what they know.
    """
    result = played(seed)

    for player in result.state.players:
        own = {
            event.sequence
            for event in payloads_of(result.journal, BallotCast)
            if isinstance(event.payload, BallotCast) and event.payload.voter == player.id
        }
        readable = {
            event.sequence
            for event in payloads_of(
                project_journal(result.journal, Recipient.of(player)), BallotCast
            )
        }

        assert own, f"{player.name} never voted, so nothing is proven"
        assert own <= readable


@pytest.mark.parametrize("seed", SAMPLE)
def test_the_channel_of_the_pack_never_reaches_a_villager(seed: int) -> None:
    """The reason a visibility model exists at all (D-007)."""
    result = played(seed)

    for player in result.state.players:
        seen = project_journal(result.journal, Recipient.of(player))
        pack_facts = payloads_of(seen, PackRevealed) + payloads_of(seen, PriorityShared)

        if player.team is Team.WEREWOLVES:
            assert pack_facts, "a wolf belongs to the channel"
        else:
            assert not pack_facts, f"{player.name} could read the pack channel"


@pytest.mark.parametrize("seed", SAMPLE)
def test_nobody_at_the_table_learns_that_an_intent_was_refused(seed: int) -> None:
    """Fumbling stays between the engine and the audience."""
    result = played_with_a_rogue(seed)

    assert payloads_of(result.journal, IntentRejected), "no refusal happened, so nothing is proven"

    for player in result.state.players:
        seen = project_journal(result.journal, Recipient.of(player))

        assert not payloads_of(seen, IntentRejected)


# --- J3.2.2 — death is public, the role of the dead is configurable ----------


@pytest.mark.parametrize("seed", CORPUS)
def test_every_death_reaches_every_single_recipient(seed: int) -> None:
    """Death is never configurable, whatever took the player (D-072)."""
    result = played(seed)
    deaths = {
        event.sequence
        for event in payloads_of(result.journal, VoteResolved)
        + payloads_of(result.journal, NightResolved)
    }
    assert deaths, "a game where nobody ever died would prove nothing here"

    for recipient in everyone_at(result.state):
        seen = {event.sequence for event in project_journal(result.journal, recipient)}

        assert deaths <= seen


@pytest.mark.parametrize("seed", SAMPLE)
def test_the_role_of_the_dead_reaches_everyone_when_it_is_revealed(seed: int) -> None:
    result = played(
        seed, rules=GameRules(information=InformationOptions(reveal_role_on_death=True))
    )
    revelations = {event.sequence for event in payloads_of(result.journal, RoleRevealed)}
    assert revelations, "nothing was revealed, so nothing is proven"

    for recipient in everyone_at(result.state):
        seen = {event.sequence for event in project_journal(result.journal, recipient)}

        assert revelations <= seen


@pytest.mark.parametrize("seed", SAMPLE)
def test_a_hidden_role_stays_hidden_even_once_its_holder_is_dead(seed: int) -> None:
    """The option decides whether the fact happens, never who may read it."""
    result = played(
        seed, rules=GameRules(information=InformationOptions(reveal_role_on_death=False))
    )

    assert not payloads_of(result.journal, RoleRevealed)
    assert any(not player.alive for player in result.state.players), "somebody did die"


# --- J3.2.3 — thought never crosses into speech (D-004) ----------------------

TABLE = (
    Player(id=PlayerId("p0"), name="Adèle", seat=0, role=RoleName.WEREWOLF),
    Player(id=PlayerId("p1"), name="Basile", seat=1, role=RoleName.WEREWOLF),
    Player(id=PlayerId("p2"), name="Camille", seat=2, role=RoleName.VILLAGER),
)

SECRET_THOUGHT = "Basile est mon complice, il ne faut surtout pas le trahir."
SECRET_NOTE = "Camille se méfie de moi depuis hier."


def a_journal_of_inner_thoughts() -> Journal:
    """A journal where every player thinks and writes, which J7 will produce."""
    journal = Journal()
    state = GameState.initial(TABLE).entering(Phase.DAY, day=2)

    for player in TABLE:
        journal.record(
            PrivateReasoningRecorded(player=player.id, reasoning=SECRET_THOUGHT), at=state
        )
        journal.record(NotebookEntryRecorded(player=player.id, note=SECRET_NOTE), at=state)
    return journal


@pytest.mark.parametrize("player", TABLE, ids=lambda player: player.name)
def test_a_player_reads_their_own_thoughts_and_nobody_elses(player: Player) -> None:
    seen = project_journal(a_journal_of_inner_thoughts().events, Recipient.of(player))
    authors = {
        event.payload.player  # type: ignore[union-attr]
        for event in seen
    }

    assert authors == {player.id}, "thought and notebook belong to their author alone"
    assert len(seen) == 2, "both of them, and only theirs"


def test_the_spectator_reads_every_inner_thought() -> None:
    """Omniscience is the point of the spectator mode (D-004)."""
    journal = a_journal_of_inner_thoughts()

    assert len(project_journal(journal.events, SPECTATOR)) == len(journal)


@pytest.mark.parametrize("player", TABLE, ids=lambda player: player.name)
def test_no_word_of_another_players_thoughts_can_be_read(player: Player) -> None:
    """Searched for as a value, so a leak under any other field name still fails."""
    others = [other for other in TABLE if other.id != player.id]
    journal = Journal()
    state = GameState.initial(TABLE).entering(Phase.DAY, day=2)
    for other in others:
        journal.record(
            PrivateReasoningRecorded(player=other.id, reasoning=SECRET_THOUGHT), at=state
        )
        journal.record(NotebookEntryRecorded(player=other.id, note=SECRET_NOTE), at=state)

    readable = leaves_of(project_journal(journal.events, Recipient.of(player)))

    assert SECRET_THOUGHT not in readable
    assert SECRET_NOTE not in readable


# --- The view handed to an agent obeys the same model ------------------------

#: The facts that move the state along. Replaying the journal up to each of them
#: rebuilds every situation a game actually went through.
STATE_CHANGING = (PhaseEntered, BallotCast, PriorityShared, VoteResolved, NightResolved)

#: Sweeping the views of a whole game means rebuilding it state by state, so
#: this runs on a few games rather than on the corpus.
FEW = range(3)


def moments_of(result: GameResult) -> list[GameState]:
    """Every situation the game went through, rebuilt from its own journal.

    Replaying rather than instrumenting the runner keeps this honest twice over:
    it sweeps the states a journal can actually produce, and it would notice a
    situation the journal fails to describe.
    """
    return [
        replay(result.journal[: rank + 1])
        for rank, event in enumerate(result.journal)
        if isinstance(event.payload, STATE_CHANGING)
    ]


@pytest.mark.parametrize("seed", FEW)
def test_no_view_ever_carries_a_role_other_than_its_viewers(seed: int) -> None:
    """The projection an agent receives is a view too (D-001, GL-3).

    Held separately from the journal on purpose: the view is what reaches a
    prompt, and nothing but a test ties the two together.
    """
    result = played(seed)

    for state in moments_of(result):
        for player in state.players:
            readable = set(scalars_in(project(state, player.id).model_dump(mode="json")))
            foreign = {role.value for role in RoleName} - {player.role.value}

            assert not (readable & foreign), f"{player.name} could read {readable & foreign}"


def test_whom_someone_named_changes_nothing_in_anybody_elses_view() -> None:
    """Two games differing only by a secret must look identical to whoever is not entitled.

    Comparing whole views is what makes this falsifiable: a field that carried
    the target — under any name, at any depth — would make them differ. Even the
    accused must not learn they were named (D-013).

    Swept over several games rather than one: a single seed can go by without a
    named ballot ever being cast, and the property would then be true of nothing
    at all. The count at the end is what refuses that.
    """
    checked = 0

    for state in (moment for seed in FEW for moment in moments_of(played(seed))):
        for rank, ballot in enumerate(state.ballots):
            if ballot.target is None:
                continue
            elsewhere = next(
                (
                    other.id
                    for other in state.living
                    if other.id not in (ballot.voter, ballot.target)
                ),
                None,
            )
            if elsewhere is None:
                continue

            altered = state.model_copy(
                update={
                    "ballots": tuple(
                        cast.model_copy(update={"target": elsewhere}) if index == rank else cast
                        for index, cast in enumerate(state.ballots)
                    )
                }
            )
            for viewer in state.players:
                if viewer.id == ballot.voter:
                    continue
                assert project(state, viewer.id) == project(altered, viewer.id)
                checked += 1

    assert checked, "no named ballot was ever compared, so nothing is proven"
