"""The three categories the engine never reads.

Agents, display and system belong to the catalogue (D-069) but are consumed by
J7, J10 and J11 rather than by a rule. They are declared, documented and
validated here; what they *do* is proven at the jalon that reads them.

Defaults are pinned whole, as the engine categories are: a field added without
a decision behind it has to fail somewhere.
"""

from lupus_ex_machina.configuration.agents import AgentOptions, Personality, SeatProfile
from lupus_ex_machina.configuration.display import DisplayOptions
from lupus_ex_machina.configuration.system import SystemOptions

# --- Agents ------------------------------------------------------------------


def test_a_seat_is_dealt_two_models_and_no_personality() -> None:
    """D-077: bidding and generation are two different quotas, so two models."""
    assert SeatProfile().model_dump() == {
        "bidding_model": "ministral-3b-latest",
        "generation_model": "mistral-small-latest",
        "temperature": 0.7,
        "top_p": 1.0,
        "personality": None,
    }


def test_the_sixteen_personalities_are_a_closed_list() -> None:
    """D-058: the list is hard-coded, so a typo cannot invent a seventeenth."""
    assert len(tuple(Personality)) == 16
    assert Personality.INTJ in tuple(Personality)


def test_seats_are_configured_one_by_one_over_a_default_profile() -> None:
    """D-058: a seat may be given its own model; the others fall back."""
    options = AgentOptions()

    assert options.default_profile == SeatProfile()
    assert options.seats == {}


def test_a_seat_that_is_configured_keeps_its_own_profile() -> None:
    profile = SeatProfile(generation_model="mistral-medium-latest")
    options = AgentOptions(seats={3: profile})

    assert options.profile_of(3) == profile
    assert options.profile_of(0) == options.default_profile


# --- Display -----------------------------------------------------------------


def test_display_defaults_to_half_a_second_per_word() -> None:
    """D-018 for the pace, D-022 for the only control the user is given."""
    assert DisplayOptions().model_dump() == {
        "seconds_per_word": 0.5,
        "manual_bubble_advance": False,
        "animations_enabled": True,
        "effects_enabled": True,
    }


# --- System ------------------------------------------------------------------


def test_system_defaults_to_a_short_first_backoff_and_no_compaction() -> None:
    """D-063 for the context, D-066 for the first step being short enough to see.

    The round budget of the runner is not here, and must not be: D-078 keeps it
    a technical net that fails loudly, never something a game can be set to.
    """
    assert SystemOptions().model_dump() == {
        "context_windows": {},
        "context_margin": 0.8,
        "backoff_first_delay_seconds": 1.0,
        "backoff_maximum_delay_seconds": 60.0,
        "backoff_attempts": 8,
        "record_journal_to": None,
    }
