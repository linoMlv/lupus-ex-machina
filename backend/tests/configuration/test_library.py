"""Saving a configuration to come back to (J6.2.3, D-068).

Files in a directory, not a database: V1 is one private game with one user
(D-045), so a folder is the whole of what is needed.

Two things are guarded here. A template carries the schema version it was
written under, so one that outlives a change is refused rather than read
wrongly. And a name is a name — never a path — because a template is named by
whoever is at the keyboard, and "../.." is a name a file system would honour.
"""

from pathlib import Path

import pytest

from lupus_ex_machina.configuration.library import (
    ConfigurationLibrary,
    InvalidTemplateNameError,
    OutdatedTemplateError,
    UnknownTemplateError,
)
from lupus_ex_machina.configuration.schema import CONFIGURATION_VERSION, GameConfiguration
from lupus_ex_machina.engine.rules import GameRules, NightOptions, TableOptions


@pytest.fixture
def library(tmp_path: Path) -> ConfigurationLibrary:
    return ConfigurationLibrary(tmp_path / "templates")


A_LONG_NIGHT = GameConfiguration(
    rules=GameRules(
        table=TableOptions(player_count=6, seed=77),
        night=NightOptions(require_werewolf_target=True),
    )
)


def test_a_saved_template_comes_back_exactly_as_it_was(library: ConfigurationLibrary) -> None:
    library.save("nuit-sans-pitie", A_LONG_NIGHT)

    assert library.load("nuit-sans-pitie") == A_LONG_NIGHT


def test_a_library_starts_empty_and_lists_what_it_holds(library: ConfigurationLibrary) -> None:
    assert library.names() == ()

    library.save("seconde", GameConfiguration())
    library.save("premiere", A_LONG_NIGHT)

    assert library.names() == ("premiere", "seconde"), "listed in an order that does not wander"


def test_saving_under_a_name_that_exists_replaces_it(library: ConfigurationLibrary) -> None:
    """Editing a template is saving it again; two files under one name is worse."""
    library.save("la-mienne", GameConfiguration())
    library.save("la-mienne", A_LONG_NIGHT)

    assert library.load("la-mienne") == A_LONG_NIGHT
    assert library.names() == ("la-mienne",)


def test_a_deleted_template_is_gone(library: ConfigurationLibrary) -> None:
    library.save("passagere", GameConfiguration())

    library.delete("passagere")

    assert library.names() == ()


def test_loading_a_template_that_was_never_saved_is_refused(
    library: ConfigurationLibrary,
) -> None:
    with pytest.raises(UnknownTemplateError, match="introuvable"):
        library.load("fantome")


def test_deleting_a_template_that_was_never_saved_is_refused(
    library: ConfigurationLibrary,
) -> None:
    with pytest.raises(UnknownTemplateError):
        library.delete("fantome")


@pytest.mark.parametrize("name", ["../evade", "dossier/nom", "", "   ", "nom\0nul", "."])
def test_a_name_that_is_really_a_path_is_refused(library: ConfigurationLibrary, name: str) -> None:
    """A template is named by a user; a name that walks the disk is not a name."""
    with pytest.raises(InvalidTemplateNameError):
        library.save(name, GameConfiguration())


def test_a_template_written_under_an_older_schema_is_refused(
    library: ConfigurationLibrary, tmp_path: Path
) -> None:
    """Refused loudly, which is the whole point of carrying a version."""
    library.save("ancienne", GameConfiguration())
    saved = tmp_path / "templates" / "ancienne.json"
    saved.write_text(
        saved.read_text().replace(f'"version": {CONFIGURATION_VERSION}', '"version": 0')
    )

    with pytest.raises(OutdatedTemplateError, match="version"):
        library.load("ancienne")


def test_a_template_is_saved_as_readable_json(
    library: ConfigurationLibrary, tmp_path: Path
) -> None:
    """A configuration one can read and fix by hand is worth the two spaces."""
    library.save("lisible", A_LONG_NIGHT)

    written = (tmp_path / "templates" / "lisible.json").read_text()

    assert '"player_count": 6' in written
