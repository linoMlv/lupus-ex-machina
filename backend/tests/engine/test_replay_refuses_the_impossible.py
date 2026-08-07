"""A journal that could not have happened is refused (D-040)."""

import pytest

from lupus_ex_machina.engine.events import (
    BallotCast,
    PhaseEntered,
    PlayerSeated,
    RoleAssigned,
)
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.replay import JournalReplayError, replay
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.state import GameState
from support.recorders import TABLE, WOLF, Recorder

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
