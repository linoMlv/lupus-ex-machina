"""The sixteen temperaments, and the one axis wired to the auction (D-058, D-064)."""

from lupus_ex_machina.configuration.agents import Personality
from lupus_ex_machina.llm.personalities import drawn_personality, personalities


def test_every_mbti_code_has_a_temperament() -> None:
    """Sixteen, because a missing one would be a seat nobody could deal."""
    assert set(personalities()) == set(Personality)


def test_a_temperament_says_who_it_is_and_how_it_plays() -> None:
    written = personalities()[Personality.ESTP]

    assert written.name
    assert len(written.description.split()) > 10, "a sentence a model can act on"


def test_extraverts_lean_towards_the_floor_and_introverts_away_from_it() -> None:
    """The mechanical half of D-064, read off the code rather than stored twice."""
    outspoken = [code for code in personalities() if code.value.startswith("E")]
    reserved = [code for code in personalities() if code.value.startswith("I")]

    assert all(personalities()[code].urgency_bias > 0 for code in outspoken)
    assert all(personalities()[code].urgency_bias < 0 for code in reserved)
    assert len(outspoken) == len(reserved) == 8


def test_a_seat_nobody_configured_is_dealt_a_temperament_from_the_seed() -> None:
    """Random by default (D-064), but a game deals the same table twice."""
    assert drawn_personality(3) is drawn_personality(3)
    assert len({drawn_personality(seed) for seed in range(16)}) == 16
