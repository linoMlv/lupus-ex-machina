"""No value a game can be set to is written into the engine (J6.3.1, D-068).

The configuration is the single source of truth, which is only true as long as
nothing quietly holds a second copy. This walks the engine looking for
module-level constants and refuses any that is not on the list below — and every
entry on that list has to say why it is not a setting.

The point is the *next* one: a constant added tomorrow fails here, and whoever
adds it has to say which of the two it is.
"""

import ast
from pathlib import Path

import pytest

import lupus_ex_machina.engine as engine

ENGINE = Path(engine.__file__).parent

#: Constants the engine is allowed to hold, each with the reason it is not a
#: setting. Structure and invariants may live here; anything a user could
#: reasonably want to change may not.
ALLOWED: dict[str, str] = {
    "phases.LEGAL_TRANSITIONS": "the phase machine itself, not a preference",
    "composition.MINIMUM_PLAYERS": "the bounds V1 deals, which the schema reads from here",
    "composition.MAXIMUM_PLAYERS": "the bounds V1 deals, which the schema reads from here",
    "composition.DEFAULT_COMPOSITIONS": "the preset tables of D-056, defaults of a setting",
    "victory.PARITY_ENDGAME_SIZE": "the victory rule is an invariant (D-059), never an option",
    "validation.BOOTSTRAP_DAY": "Day 1 is a rule of the bootstrap (D-032), not a length",
    "validation.ACTIONABLE_PHASES": "which phases take an intent at all — structure",
    "roles.ONE_SHOT_ACTIONS": "which powers work once in a game — a property of the roles",
    "roles.ROLES": "the declarative registry of D-010",
    "names.FIRST_NAMES": "the pool names are drawn from (D-042)",
    "visibility.SPECTATOR": "the omniscient recipient of D-009",
    "persistence.ENCODING": "how a file is written, not how a game is played",
    "runner.DEFAULT_MAX_ROUNDS": (
        "the technical net of D-078, which must never become a rule of the game"
    ),
    "runner.Agents": "a type alias",
    "runner.Resolver": "a type alias",
    "runner.Announcement": "a type alias",
    "rng.Rng": "a type alias",
    "events.EventPayload": "a type alias",
    "intents.Intent": "a type alias",
    "journal.Clock": "a type alias",
    "players.PlayerId": "a type alias",
}


def constants_of(module: Path) -> list[str]:
    """Every module-level name assigned in that file, in source order."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    found = []
    for statement in tree.body:
        match statement:
            case ast.Assign(targets=[ast.Name(id=name)]):
                found.append(name)
            case ast.AnnAssign(target=ast.Name(id=name)):
                found.append(name)
    return found


def engine_constants() -> dict[str, str]:
    """Every module-level constant of the engine, keyed by ``module.NAME``."""
    return {
        f"{module.stem}.{name}": module.stem
        for module in sorted(ENGINE.glob("*.py"))
        for name in constants_of(module)
    }


def test_the_engine_holds_no_value_a_game_could_be_set_to() -> None:
    """Anything not on the list is either a setting, or a reason to add one."""
    unexplained = sorted(set(engine_constants()) - set(ALLOWED))

    assert unexplained == [], (
        "these engine constants are unaccounted for: either move them into the "
        "configuration schema (D-068), or add them to ALLOWED with the reason "
        "they are not a setting"
    )


def test_the_list_of_allowed_constants_has_not_outlived_the_code() -> None:
    """A list that names constants nobody holds any more stops being read."""
    stale = sorted(set(ALLOWED) - set(engine_constants()))

    assert stale == []


@pytest.mark.parametrize("name", sorted(ALLOWED))
def test_every_allowed_constant_says_why_it_is_not_a_setting(name: str) -> None:
    assert ALLOWED[name].strip()
