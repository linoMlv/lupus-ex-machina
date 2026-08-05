"""The configurations the application ships with (J6.2.4).

Three games worth playing without setting anything up: the decided one, one
that helps the village, and one that tells it nothing. They exist so the form
of J11 opens on something rather than on forty controls, and so the options that
matter most have a demonstrated effect.

Each is a whole configuration rather than a patch: a preset that only listed its
differences would drift the day a default moves.
"""

import pytest

from lupus_ex_machina.configuration.presets import PRESETS, UnknownPresetError, preset
from lupus_ex_machina.configuration.schema import CONFIGURATION_VERSION, GameConfiguration


def test_three_presets_are_shipped() -> None:
    assert len(PRESETS) == 3


def test_every_preset_is_a_complete_and_current_configuration() -> None:
    """Loadable as they are, with no default left to guess at."""
    for shipped in PRESETS:
        assert shipped.configuration.version == CONFIGURATION_VERSION


def test_every_preset_says_in_french_what_it_changes() -> None:
    """They are read on screen, so they are written in French (HR-6)."""
    for shipped in PRESETS:
        assert shipped.label.strip()
        assert shipped.summary.strip()


def test_presets_are_named_apart() -> None:
    assert len({shipped.name for shipped in PRESETS}) == len(PRESETS)
    assert len({shipped.label for shipped in PRESETS}) == len(PRESETS)


def test_the_classic_preset_is_the_decided_game() -> None:
    """The defaults of the schema, unedited: the two must not drift apart."""
    assert preset("classic").configuration == GameConfiguration()


def test_the_helpful_preset_hands_the_village_more_than_the_classic_one() -> None:
    """A smaller table, and a seer who says out loud what she read (D-031)."""
    rules = preset("initiation").configuration.rules

    assert rules.table.player_count == 6
    assert rules.roles.speaking_seer is True


def test_the_dark_preset_tells_the_table_as_little_as_the_rules_allow() -> None:
    """Nothing revealed, and a pack that may not leave empty-handed (D-078)."""
    rules = preset("dark_night").configuration.rules

    assert rules.information.reveal_role_on_death is False
    assert rules.information.reveal_ballots_at_the_count is False
    assert rules.roles.seer_learns_exact_role is False
    assert rules.night.require_werewolf_target is True


def test_a_preset_nobody_ships_is_refused() -> None:
    with pytest.raises(UnknownPresetError, match="inconnu"):
        preset("la-mienne")
