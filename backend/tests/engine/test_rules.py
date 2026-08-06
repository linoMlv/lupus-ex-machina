"""The rules a game is played by.

These are the six categories of D-069 the engine itself reads, held in one
record so that a game carries the rules it is played by (D-068). The defaults
are pinned value by value: each one is a decision, and a decision that drifts
without anybody noticing is the thing this file exists to prevent.

The whole dump of each category is compared rather than a field at a time, so a
field added without a decision behind it fails here — the catalogue of J6 is the
specification, not a starting point.
"""

from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.rules import (
    DebateOptions,
    GameMode,
    GameRules,
    InformationOptions,
    NightOptions,
    RoleOptions,
    TableOptions,
    VoteOptions,
)

# --- The decided defaults ----------------------------------------------------


def test_a_table_defaults_to_eight_seats_dealt_from_the_preset() -> None:
    """D-056 for the size, D-061 for the freedom to write one's own."""
    assert TableOptions().model_dump() == {
        "player_count": 8,
        "composition": None,
        "seed": 1,
        "mode": GameMode.SPECTATOR,
        "human_seat": None,
    }


def test_the_roles_default_to_the_generous_reading_of_their_powers() -> None:
    """D-029, D-031, D-054, D-055: the poorer settings are deliberate handicaps."""
    assert RoleOptions().model_dump() == {
        "seer_learns_exact_role": True,
        "speaking_seer": False,
        "witch_may_save_herself": True,
        "hunter_must_shoot": True,
    }


def test_information_defaults_to_what_the_table_is_told() -> None:
    """D-080 and D-082, both settled by the project owner on 2026-08-05.

    The role of the deceased is announced, as classic Werewolf does: it is the
    main engine of information the village has to work with. Death itself was
    never configurable — it is always public (D-072).
    """
    assert InformationOptions().model_dump() == {
        "reveal_role_on_death": True,
        "reveal_ballots_at_the_count": True,
        "reveal_priorities_at_the_designation": True,
        "public_vote_history": True,
        "show_personalities": True,
    }


def test_the_debate_defaults_to_the_coefficients_of_the_protocol() -> None:
    """D-002 for the arbitration, D-021 for the word limits, GL-7 for the ceiling."""
    assert DebateOptions().model_dump() == {
        "addressed_bonus": 25,
        "accused_bonus": 40,
        "recency_penalty": 30,
        "recency_window": 3,
        "word_quota": 300,
        "quota_penalty": 50,
        "minimum_urgency": 0,
        "waiting_allowed": True,
        "turns_per_player_per_day": 5,
        "speech_word_limit": 50,
        "analysis_word_limit": 40,
        "notebook_word_limit": 20,
        "notebook_note_limit": 30,
    }


def test_a_tied_vote_defaults_to_one_silent_runoff() -> None:
    """D-050 and D-062, and a debate nobody has called time on (D-048)."""
    assert VoteOptions().model_dump() == {
        "hold_a_runoff_on_a_tie": True,
        "turns_before_forced_vote": None,
    }


def test_the_night_defaults_to_a_pack_free_to_take_nobody() -> None:
    """D-078 for the freedom, D-008 for the budget, D-006 for the order."""
    assert NightOptions().model_dump() == {
        "require_werewolf_target": False,
        "priority_budget": 100,
        "hold_a_runoff_on_a_tie": True,
        "wake_order": (RoleName.SEER, RoleName.WEREWOLF, RoleName.WITCH),
    }


# --- What the engine is handed ------------------------------------------------


def test_the_rules_of_a_game_are_the_six_categories_the_engine_reads() -> None:
    """One record, so a game carries the rules it is played by rather than six."""
    rules = GameRules()

    assert (rules.table, rules.roles, rules.information) == (
        TableOptions(),
        RoleOptions(),
        InformationOptions(),
    )
    assert (rules.debate, rules.vote, rules.night) == (
        DebateOptions(),
        VoteOptions(),
        NightOptions(),
    )
