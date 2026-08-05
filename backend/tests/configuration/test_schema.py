"""The root of the configuration schema.

The schema is the single source of truth of what a game may be set to (D-068):
the front end derives its form from it, and the engine reads its values. Two
things are asked of the root itself — that it be complete without anybody
filling anything in, and that it say which version of the schema it follows, so
a saved template that outlives a change fails loudly instead of quietly.
"""

import pytest
from pydantic import ValidationError

from lupus_ex_machina.configuration.agents import AgentOptions
from lupus_ex_machina.configuration.display import DisplayOptions
from lupus_ex_machina.configuration.schema import CONFIGURATION_VERSION, GameConfiguration
from lupus_ex_machina.configuration.system import SystemOptions
from lupus_ex_machina.engine.rules import GameRules


def test_a_configuration_is_complete_without_being_told_anything() -> None:
    """Every default lives in the schema, never in the code that reads it."""
    assert GameConfiguration() == GameConfiguration()


def test_a_configuration_says_which_version_of_the_schema_it_follows() -> None:
    """A template saved today has to be readable, or refused, tomorrow."""
    assert GameConfiguration().version == CONFIGURATION_VERSION


def test_a_configuration_holds_the_nine_categories_of_the_catalogue() -> None:
    """D-069: six the engine reads, three read by J7, J10 and J11.

    The engine ones are gathered under ``rules`` because that is exactly what a
    game is handed; the others would drag the models and the staging into the
    engine along with them.
    """
    configuration = GameConfiguration()

    assert configuration.rules == GameRules()
    assert (configuration.agents, configuration.display, configuration.system) == (
        AgentOptions(),
        DisplayOptions(),
        SystemOptions(),
    )


def test_a_configuration_cannot_be_altered_once_it_is_built() -> None:
    """A game reads its configuration many times; it must read the same one."""
    configuration = GameConfiguration()

    with pytest.raises(ValidationError):
        configuration.version = CONFIGURATION_VERSION + 1
