"""The JSON Schema the front end builds its form from (J6.2.1, J6.2.2).

Generated from the model, never written by hand (D-068): a copy would drift, and
the drift would show up as a form that sets options the backend does not have.

The snapshot beside these tests is what makes a change to the schema visible in
review. It is not a second source of truth — nothing reads it but this file —
it is a tripwire: rename a key or drop a category, and the diff says so.
"""

import json
import os
from pathlib import Path
from typing import Any

from lupus_ex_machina.configuration.schema import GameConfiguration

SNAPSHOT = Path(__file__).parent / "snapshots" / "configuration.schema.json"

#: Set to rewrite the snapshot after an intended change:
#: ``UPDATE_SNAPSHOTS=1 uv run pytest tests/configuration/test_json_schema.py``
UPDATE = "UPDATE_SNAPSHOTS"


def schema() -> dict[str, Any]:
    return GameConfiguration.model_json_schema()


def test_the_schema_is_generated_from_the_model() -> None:
    """Nine categories, and the version a saved template is read against."""
    properties = schema()["properties"]

    assert set(properties) == {"version", "rules", "agents", "display", "system"}


def test_the_categories_are_titled_in_french_for_the_form() -> None:
    """Keys are code and stay English; what a user reads is French (HR-6)."""
    properties = schema()["properties"]

    assert properties["display"]["title"] == "Affichage et rythme"
    assert properties["system"]["title"] == "Système"


def test_the_six_categories_the_engine_reads_are_titled_too() -> None:
    rules = schema()["$defs"]["GameRules"]["properties"]

    assert [rules[key]["title"] for key in ("table", "roles", "information")] == [
        "Partie",
        "Rôles",
        "Information et visibilité",
    ]
    assert [rules[key]["title"] for key in ("debate", "vote", "night")] == [
        "Débat et parole",
        "Vote",
        "Nuit",
    ]


def test_the_schema_carries_the_descriptions_and_the_defaults() -> None:
    """What the form needs to render a control without asking anybody."""
    table = schema()["$defs"]["TableOptions"]["properties"]

    assert table["player_count"]["default"] == 8
    assert "6 à 8" in table["player_count"]["description"]


def test_the_schema_has_not_changed_without_anybody_saying_so() -> None:
    """A tripwire, not a source of truth: rename a key and this says so."""
    generated = schema()
    if os.environ.get(UPDATE):  # pragma: no cover - a developer's escape hatch
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(generated, indent=2, ensure_ascii=False) + "\n")

    assert SNAPSHOT.exists(), f"run with {UPDATE}=1 to write the first snapshot"
    assert generated == json.loads(SNAPSHOT.read_text()), (
        f"the schema changed; if that was intended, rerun with {UPDATE}=1"
    )
