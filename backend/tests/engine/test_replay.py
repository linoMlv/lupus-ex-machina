"""Rebuilding a game from its journal.

The state is derived from the journal, never the other way round (D-040). That
is what makes the journal the source of truth rather than a log: if a state can
exist that the journal does not produce, then information exists that was never
given an audience.

Replay validates as it goes. A journal that could not have been produced by a
real game is refused rather than turned into a plausible-looking state — a
truncated file is a thing that happens, and a silently wrong game is worse than
a loud failure.
"""

import pytest

from lupus_ex_machina.engine.events import (
    BallotAnnounced,
    BallotCast,
    EventPayload,
    GameEnded,
    IntentRejected,
    NightResolved,
    NotebookEntryRecorded,
    PackRevealed,
    PhaseEntered,
    PlayerSeated,
    PriorityShared,
    PrivateReasoningRecorded,
    RoleAssigned,
    RoleRevealed,
    SpeechDelivered,
    VoteResolved,
)
from lupus_ex_machina.engine.intents import PriorityPoint
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.replay import JournalReplayError, replay
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.state import GameState, Speech
from lupus_ex_machina.engine.victory import Outcome

WOLF = Player(id=PlayerId("p0"), name="Adèle", seat=0, role=RoleName.WEREWOLF)
VILLAGER = Player(id=PlayerId("p1"), name="Basile", seat=1, role=RoleName.VILLAGER)
OTHER_VILLAGER = Player(id=PlayerId("p2"), name="Camille", seat=2, role=RoleName.VILLAGER)

TABLE = (WOLF, VILLAGER, OTHER_VILLAGER)


class Recorder:
    """Writes a journal the way the engine does, for a table known in advance."""

    def __init__(self) -> None:
        """Seat the table and deal the roles."""
        self.journal = Journal()
        self.state = GameState.initial(TABLE)

        for player in TABLE:
            self._write(PlayerSeated(player=player.id, name=player.name, seat=player.seat))
        for player in TABLE:
            self._write(RoleAssigned(player=player.id, role=player.role))
        self._write(PackRevealed(members=(WOLF.id,)))
        self._write(PhaseEntered(phase=Phase.NIGHT_ZERO, day=0))

    def _write(self, payload: EventPayload) -> None:
        self.journal.record(payload, at=self.state)

    def enter(self, phase: Phase, *, day: int | None = None) -> "Recorder":
        """Move to another phase, exactly as the engine would."""
        self.state = self.state.entering(phase, day=day)
        self._write(PhaseEntered(phase=self.state.phase, day=self.state.day))
        return self

    def write(self, payload: EventPayload) -> "Recorder":
        """Record one more fact."""
        self._write(payload)
        return self


def test_a_journal_of_a_freshly_dealt_game_rebuilds_the_opening_state() -> None:
    rebuilt = replay(Recorder().journal.events)

    assert rebuilt == GameState.initial(TABLE)


def test_replay_restores_the_roles_the_table_never_saw() -> None:
    """Roles are private facts, and the state cannot be rebuilt without them."""
    rebuilt = replay(Recorder().journal.events)

    assert rebuilt.player(WOLF.id).role is RoleName.WEREWOLF
    assert rebuilt.player(VILLAGER.id).role is RoleName.VILLAGER


def test_replay_restores_the_ballots_of_the_round() -> None:
    recorder = Recorder().enter(Phase.DAY, day=2)
    recorder.write(BallotCast(voter=VILLAGER.id, target=WOLF.id))
    recorder.write(BallotAnnounced(voter=VILLAGER.id))
    recorder.write(BallotCast(voter=WOLF.id, target=None))

    rebuilt = replay(recorder.journal.events)

    assert [(ballot.voter, ballot.target) for ballot in rebuilt.ballots] == [
        (VILLAGER.id, WOLF.id),
        (WOLF.id, None),
    ]


def test_replay_restores_what_the_pack_designated() -> None:
    recorder = Recorder().enter(Phase.DAY, day=1).enter(Phase.RESOLUTION).enter(Phase.NIGHT)
    recorder.write(
        PriorityShared(actor=WOLF.id, allocations=(PriorityPoint(target=VILLAGER.id, points=60),))
    )

    rebuilt = replay(recorder.journal.events)

    assert rebuilt.has_acted_tonight(WOLF.id)


def test_a_resolved_vote_kills_and_closes_the_round() -> None:
    recorder = Recorder().enter(Phase.DAY, day=2)
    recorder.write(BallotCast(voter=VILLAGER.id, target=WOLF.id))
    recorder.enter(Phase.RESOLUTION).write(VoteResolved(eliminated=WOLF.id))

    rebuilt = replay(recorder.journal.events)

    assert not rebuilt.is_alive(WOLF.id)
    assert rebuilt.ballots == (), "a resolved round carries no ballot over"


def test_a_resolved_night_kills_its_victim() -> None:
    recorder = Recorder().enter(Phase.DAY, day=1).enter(Phase.RESOLUTION).enter(Phase.NIGHT)
    recorder.write(
        PriorityShared(actor=WOLF.id, allocations=(PriorityPoint(target=VILLAGER.id, points=60),))
    )
    recorder.enter(Phase.RESOLUTION).write(NightResolved(victims=(VILLAGER.id,)))

    rebuilt = replay(recorder.journal.events)

    assert not rebuilt.is_alive(VILLAGER.id)
    assert rebuilt.priority_shares == ()


def test_a_tie_that_spared_everyone_replays_as_such() -> None:
    """A resolution without a victim is a fact of its own (D-050)."""
    recorder = Recorder().enter(Phase.DAY, day=2).enter(Phase.RESOLUTION)
    recorder.write(VoteResolved(eliminated=None))

    rebuilt = replay(recorder.journal.events)

    assert len(rebuilt.living) == len(TABLE)


def test_a_replayed_turn_at_the_floor_is_given_back_to_the_round() -> None:
    """A replayed round gets its turns at the floor back.

    The auction is scored against them (D-002). Rebuilt without them, a game
    would arbitrate differently from the one it claims to be replaying.
    """
    recorder = Recorder().enter(Phase.DAY, day=2)
    recorder.write(
        SpeechDelivered(
            speaker=WOLF.id, speech="Camille, tu mens.", addressed=VILLAGER.id, accused=VILLAGER.id
        )
    )

    rebuilt = replay(recorder.journal.events)

    assert rebuilt.floor == (
        Speech(speaker=WOLF.id, words=3, addressed=VILLAGER.id, accused=VILLAGER.id),
    )


def test_facts_that_change_nothing_leave_the_state_alone() -> None:
    """Thoughts and announcements are information, not effects."""
    recorder = Recorder().enter(Phase.DAY, day=2)
    plain = replay(recorder.journal.events)

    recorder.write(BallotAnnounced(voter=WOLF.id))
    recorder.write(RoleRevealed(player=VILLAGER.id, role=RoleName.VILLAGER))
    recorder.write(IntentRejected(actor=WOLF.id, reason="already voted"))
    recorder.write(PrivateReasoningRecorded(player=WOLF.id, reasoning="Camille me gêne."))
    recorder.write(NotebookEntryRecorded(player=WOLF.id, note="Camille pivote vite."))
    recorder.write(GameEnded(outcome=Outcome.VILLAGE_WINS))

    assert replay(recorder.journal.events) == plain


# --- A journal that could not have happened is refused ------------------------


def test_an_empty_journal_has_no_game_to_rebuild() -> None:
    with pytest.raises(JournalReplayError, match="no game"):
        replay(())


def test_a_journal_that_never_opened_a_phase_has_no_game_to_rebuild() -> None:
    recorder = Journal()
    state = GameState.initial(TABLE)
    recorder.record(PlayerSeated(player=WOLF.id, name=WOLF.name, seat=0), at=state)

    with pytest.raises(JournalReplayError, match="no game"):
        replay(recorder.events)


def test_a_game_cannot_open_on_anything_but_night_zero() -> None:
    recorder = Journal()
    state = GameState.initial(TABLE)
    for player in TABLE:
        recorder.record(
            PlayerSeated(player=player.id, name=player.name, seat=player.seat), at=state
        )
        recorder.record(RoleAssigned(player=player.id, role=player.role), at=state)
    recorder.record(PhaseEntered(phase=Phase.DAY, day=1), at=state)

    with pytest.raises(JournalReplayError, match="Night 0"):
        replay(recorder.events)


def test_a_role_dealt_to_someone_who_never_sat_down_is_refused() -> None:
    recorder = Journal()
    state = GameState.initial(TABLE)
    recorder.record(RoleAssigned(player=PlayerId("ghost"), role=RoleName.VILLAGER), at=state)

    with pytest.raises(JournalReplayError, match="never took a seat"):
        replay(recorder.events)


def test_a_table_where_someone_was_never_dealt_a_role_is_refused() -> None:
    """Seats are public and roles are not, so a filtered journal is missing them.

    Rebuilding a state from what a *player* may read would quietly produce a
    game with the wrong table; it has to be refused instead.
    """
    recorder = Journal()
    state = GameState.initial(TABLE)
    for player in TABLE:
        recorder.record(
            PlayerSeated(player=player.id, name=player.name, seat=player.seat), at=state
        )
    recorder.record(RoleAssigned(player=WOLF.id, role=WOLF.role), at=state)
    recorder.record(PhaseEntered(phase=Phase.NIGHT_ZERO, day=0), at=state)

    with pytest.raises(JournalReplayError, match="No role was ever dealt"):
        replay(recorder.events)


def test_a_fact_about_a_game_that_has_not_started_is_refused() -> None:
    recorder = Journal()
    state = GameState.initial(TABLE)
    recorder.record(BallotCast(voter=WOLF.id, target=None), at=state)

    with pytest.raises(JournalReplayError, match="not started"):
        replay(recorder.events)


def test_an_impossible_sequence_of_phases_is_refused() -> None:
    """Replay walks the same state machine as the game, so it catches this."""
    recorder = Recorder()
    recorder.journal.record(PhaseEntered(phase=Phase.ENDED, day=0), at=recorder.state)

    with pytest.raises(JournalReplayError, match="not allowed"):
        replay(recorder.journal.events)


def test_a_player_seated_twice_is_refused() -> None:
    """Two facts about one seat mean the journal is not the game it claims to be."""
    recorder = Recorder()
    recorder.write(PlayerSeated(player=WOLF.id, name="Imposteur", seat=0))

    with pytest.raises(JournalReplayError, match="twice"):
        replay(recorder.journal.events)
