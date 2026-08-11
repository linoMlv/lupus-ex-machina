"""No option is declared that nothing reads (J8.0.4, D-092).

`test_every_option_is_observable` proves one option of each of the six
categories the engine reads. It says so itself — and that is exactly where the
defect of J7 hid: the backoff delays were declared, validated and documented in
the *system* category, and no line of code ever looked at them. The guard of the
constants does not reach there either, since it only walks `engine/`.

So this one walks the schema instead of the code: every field of every category,
checked against the source for somebody who reads it. Anything nobody reads has
to be on the list below, with the reason — a form control that changes nothing
is a lie told to whoever sets it, and the point is the *next* one.
"""

from pathlib import Path

import pytest
from pydantic import BaseModel

import lupus_ex_machina
from lupus_ex_machina.configuration.schema import GameConfiguration

SOURCE = Path(lupus_ex_machina.__file__).parent

#: Where the options are *declared*. A field found only here is a field nobody
#: reads: without this the guard would count every declaration as its own
#: reader, and would pass while proving nothing.
DECLARATIONS = (("configuration",), ("engine", "rules"))

#: Options nothing reads yet, each with the reason. Every entry is a promise
#: with a jalon against it, or a defect somebody has to settle.
UNREAD: dict[str, str] = {
    "display.seconds_per_word": "the pace of a bubble, read by the staging of J10 (D-018)",
    "display.manual_bubble_advance": "the one display control of D-022, read by J10",
    "display.animations_enabled": "staging, read by J10 (D-076)",
    "display.effects_enabled": "staging, read by J10 (D-019)",
    "rules.information.show_personalities": (
        "what a spectator is shown of a temperament, read by J11 (D-064)"
    ),
}


def fields_of(model: type[BaseModel], prefix: str = "") -> list[str]:
    """Every leaf field of that model, dotted through the categories it nests."""
    found: list[str] = []
    for name, info in model.model_fields.items():
        annotation = info.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            found.extend(fields_of(annotation, f"{prefix}{name}."))
        else:
            found.append(f"{prefix}{name}")
    return found


def declares(module: Path, root: Path) -> bool:
    """Whether that module is where options are written down rather than read."""
    parts = module.relative_to(root).parts
    return any(parts[: len(where)] == where for where in DECLARATIONS)


def readers_of(field: str, root: Path) -> list[str]:
    """Every module outside the declarations that names that field."""
    leaf = field.rsplit(".", 1)[-1]
    return [
        str(module.relative_to(root))
        for module in sorted(root.rglob("*.py"))
        if not declares(module, root) and leaf in module.read_text(encoding="utf-8")
    ]


def unread_options() -> list[str]:
    """Every option of the schema that no module outside its declaration names."""
    return [field for field in fields_of(GameConfiguration) if not readers_of(field, SOURCE)]


def test_an_option_is_never_its_own_reader(tmp_path: Path) -> None:
    """Without this, the guard would pass while proving nothing at all.

    Every field is named in the module that declares it — that is what declaring
    is. A scan that counted those would find a reader for everything and never
    fail, which is the shape of hollow test this project has met four times.
    """
    (tmp_path / "configuration").mkdir()
    (tmp_path / "configuration" / "system.py").write_text(
        "backoff_attempts: int = 8", encoding="utf-8"
    )
    (tmp_path / "elsewhere.py").write_text("read = options.context_margin", encoding="utf-8")

    assert readers_of("system.backoff_attempts", tmp_path) == []
    assert readers_of("system.context_margin", tmp_path) == ["elsewhere.py"]


def test_every_option_of_the_schema_is_read_somewhere() -> None:
    """Anything not on the list is either wired up, or a reason to write one down."""
    unexplained = sorted(set(unread_options()) - set(UNREAD))

    assert unexplained == [], (
        "these options are declared and nothing reads them: either wire them up, "
        "or add them to UNREAD with the jalon that will, or the defect they are"
    )


def test_the_list_has_not_outlived_the_code() -> None:
    """A list naming options that are read by now stops being read itself."""
    stale = sorted(set(UNREAD) - set(unread_options()))

    assert stale == []


@pytest.mark.parametrize("field", sorted(UNREAD))
def test_every_unread_option_says_why_nothing_reads_it(field: str) -> None:
    assert UNREAD[field].strip()
