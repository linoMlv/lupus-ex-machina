"""What a played game writes down, and what that journal gives back.

This is the criterion the jalon is judged on: replaying the journal of a game
must reconstruct that exact game (D-040). It is checked on the hundred scripted
games of J2.5.5 rather than on a scenario — a corpus catches the fact somebody
forgot to record, which a hand-written case never does, because the hand that
wrote the case is the hand that forgot.
"""

import pytest

from lupus_ex_machina.agents.scripted import AlwaysAccuseAgent, RandomAgent, RogueAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.events import (
    BallotAnnounced,
    BallotCast,
    Fact,
    GameEnded,
    IntentRejected,
    NightResolved,
    PackRevealed,
    PhaseEntered,
    PlayerSeated,
    RoleAssigned,
    RoleRevealed,
    ShotFired,
    SpeechDelivered,
    VoteResolved,
)
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.policy import InformationPolicy
from lupus_ex_machina.engine.replay import replay
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.roles import Team, team_of
from lupus_ex_machina.engine.runner import GameResult, play_game
from lupus_ex_machina.engine.setup import create_game

CORPUS = range(100)


def play(
    seed: int,
    *,
    player_count: int = 8,
    policy: InformationPolicy | None = None,
) -> GameResult:
    """Play one full game of random agents, journalling everything."""
    rng = create_rng(seed)
    state = create_game(player_count, rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: RandomAgent(rng=rng) for player in state.players}
    return play_game(state, agents, journal=Journal(), policy=policy)


def facts_of[FactT: Fact](result: GameResult, kind: type[FactT]) -> list[FactT]:
    """Every fact of that kind the game recorded, narrowed to it."""
    return [event.payload for event in result.journal if isinstance(event.payload, kind)]


# --- The journal is the game ------------------------------------------------


def test_a_played_game_writes_a_journal() -> None:
    result = play(seed=1)

    assert result.journal, "a game that recorded nothing has no source of truth"


@pytest.mark.parametrize("seed", CORPUS)
def test_replaying_the_journal_reconstructs_the_game_exactly(seed: int) -> None:
    """The criterion of the jalon: nothing happened that was not written down."""
    result = play(seed)

    assert replay(result.journal) == result.state


def test_the_journal_opens_by_seating_the_table_and_dealing_the_roles() -> None:
    result = play(seed=1)

    assert len(facts_of(result, PlayerSeated)) == len(result.state.players)
    assert len(facts_of(result, RoleAssigned)) == len(result.state.players)
    assert len(facts_of(result, PackRevealed)) == 1


def test_the_pack_is_introduced_to_itself_and_to_nobody_else() -> None:
    """Wolves meet on Night 0 (D-032); the fact carries the audience to prove it."""
    result = play(seed=1)
    introduction = facts_of(result, PackRevealed)[0]

    assert set(introduction.members) == {
        player.id for player in result.state.players if player.team is Team.WEREWOLVES
    }


def test_the_journal_opens_on_night_zero() -> None:
    result = play(seed=1)
    first_phase = facts_of(result, PhaseEntered)[0]

    assert first_phase.phase is Phase.NIGHT_ZERO


def test_the_journal_closes_on_the_outcome_of_the_game() -> None:
    result = play(seed=1)
    ending = facts_of(result, GameEnded)[-1]

    assert ending.outcome is result.outcome
    assert result.journal[-1].phase is Phase.ENDED


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_every_vote_is_both_announced_and_recorded(seed: int) -> None:
    """Two audiences, therefore two facts (D-013, D-051)."""
    result = play(seed)

    assert [ballot.voter for ballot in facts_of(result, BallotCast)] == [
        announcement.voter for announcement in facts_of(result, BallotAnnounced)
    ]


def test_speech_reaches_the_journal() -> None:
    result = play(seed=1)

    assert facts_of(result, SpeechDelivered), "the shared transcript is born here"


def test_every_death_is_written_down() -> None:
    """Death is public and always recorded, whatever took the player (D-072)."""
    result = play(seed=1)
    dead = {player.id for player in result.state.players if not player.alive}

    recorded = (
        {vote.eliminated for vote in facts_of(result, VoteResolved)}
        | {victim for night in facts_of(result, NightResolved) for victim in night.victims}
        | {shot.target for shot in facts_of(result, ShotFired)}
    )

    assert dead <= {victim for victim in recorded if victim is not None}


def test_a_refused_intent_is_written_down_for_the_audience_alone() -> None:
    """The raw material for judging how models behave in J7."""
    rng = create_rng(9)
    state = create_game(8, rng=rng)
    agents: dict[PlayerId, Agent] = {
        player.id: RogueAgent() if player.seat == 0 else RandomAgent(rng=rng)
        for player in state.players
    }

    result = play_game(state, agents, journal=Journal())

    assert len(facts_of(result, IntentRejected)) == result.rejected_intents
    assert result.rejected_intents > 0


def test_a_game_played_without_a_journal_still_runs() -> None:
    """Journalling is not a burden the caller must carry to play a game."""
    rng = create_rng(5)
    state = create_game(6, rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: AlwaysAccuseAgent() for player in state.players}

    result = play_game(state, agents)

    assert result.journal, "one is opened for it"


# --- The role of the dead follows the configuration (D-072) ------------------


def test_the_role_of_the_dead_is_revealed_when_the_configuration_says_so() -> None:
    result = play(seed=1, policy=InformationPolicy(reveal_role_on_death=True))
    revealed = {revelation.player: revelation.role for revelation in facts_of(result, RoleRevealed)}
    dead = {player.id: player.role for player in result.state.players if not player.alive}

    assert revealed == dead


def test_the_role_of_the_dead_stays_hidden_when_the_configuration_says_so() -> None:
    """Death itself is never hidden — only what the deceased was (D-072)."""
    result = play(seed=1, policy=InformationPolicy(reveal_role_on_death=False))

    assert facts_of(result, RoleRevealed) == []
    assert facts_of(result, VoteResolved), "deaths are recorded all the same"


def test_a_revelation_names_the_role_the_player_actually_held() -> None:
    result = play(seed=2, policy=InformationPolicy(reveal_role_on_death=True))

    for revelation in facts_of(result, RoleRevealed):
        assert result.state.player(revelation.player).role is revelation.role


def test_by_default_a_death_reveals_nothing() -> None:
    """The engine picks the discreet default; J6 makes it a knob."""
    assert InformationPolicy().reveal_role_on_death is False


def test_a_revelation_is_recorded_whichever_side_the_dead_belonged_to() -> None:
    """Guard against a revelation that would only ever fire for one team.

    Stated in teams rather than in role names: what matters is that neither side
    is silently spared the announcement, and the roster of roles grows.
    """
    revealed_teams = {
        team_of(revelation.role)
        for seed in (1, 2, 3, 4)
        for revelation in facts_of(
            play(seed, policy=InformationPolicy(reveal_role_on_death=True)), RoleRevealed
        )
    }

    assert revealed_teams == {Team.VILLAGE, Team.WEREWOLVES}
