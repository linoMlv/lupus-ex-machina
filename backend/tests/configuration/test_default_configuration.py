"""What the configuration nobody touched is worth (J6.1.5).

Two things are asked of it. It has to play — a default that needs correcting
before a game runs is not a default. And it has to be *readable*: the front end
derives its form from the schema (D-068), so a field with no description reaches
the screen as a bare key, which is how an option nobody understands ends up
being left alone.
"""

from pydantic import BaseModel

from lupus_ex_machina.agents.scripted import RandomAgent
from lupus_ex_machina.configuration.schema import GameConfiguration
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.runner import play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.victory import Outcome


async def test_the_default_configuration_plays_a_whole_game() -> None:
    """From nothing but the schema to a finished game (D-068)."""
    configuration = GameConfiguration()
    rng = create_rng(configuration.rules.table.seed)

    state = create_game(configuration.rules, rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: RandomAgent(rng=rng) for player in state.players}
    result = await play_game(state, agents)

    assert result.outcome in {Outcome.VILLAGE_WINS, Outcome.WEREWOLVES_WIN}
    assert result.state.rules == configuration.rules, "the game was played by what was configured"


def every_field_of(model: type[BaseModel], path: str = "") -> list[tuple[str, str | None]]:
    """Every leaf field of a model and its nested categories, with its description."""
    found: list[tuple[str, str | None]] = []
    for name, field in model.model_fields.items():
        full = f"{path}{name}"
        nested = field.annotation
        if isinstance(nested, type) and issubclass(nested, BaseModel):
            found.extend(every_field_of(nested, f"{full}."))
        else:
            found.append((full, field.description))
    return found


def test_every_option_of_the_catalogue_is_documented() -> None:
    """A field with no description is an unlabelled control in the form of J11."""
    undocumented = [
        name for name, description in every_field_of(GameConfiguration) if not description
    ]

    assert undocumented == []


def test_the_catalogue_is_not_empty_in_any_of_its_nine_categories() -> None:
    """Guards the test above from passing on a schema that walked nothing."""
    documented = {name for name, _ in every_field_of(GameConfiguration)}
    categories = {name.rsplit(".", 1)[0] for name in documented if "." in name}

    assert len(documented) > 30
    assert categories == {
        "agents",
        "rules.table",
        "rules.roles",
        "rules.information",
        "rules.debate",
        "rules.vote",
        "rules.night",
        "agents.default_profile",
        "display",
        "system",
    }
