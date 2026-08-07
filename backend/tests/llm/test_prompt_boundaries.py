"""What the system prompt says, what it holds back, and where prompts live.

The leak this file is really about: a prompt holds nothing the view does
not, compared whole rather than field by field (J7.2, GL-3).
"""

import ast
import pathlib

import pytest

import lupus_ex_machina.llm
from lupus_ex_machina.engine.journal import Journal, project_journal
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.views import project
from lupus_ex_machina.engine.visibility import Recipient
from lupus_ex_machina.llm.prompting import bid_prompt, system_prompt, turn_prompt
from support.prompts import (
    A_PERSONALITY,
    OTHER,
    SEER,
    VILLAGER,
    WOLF,
    a_game,
    briefing,
)

# --- What the system prompt has to say (J7.2.2) ------------------------------


def test_the_system_prompt_states_the_rules_the_role_and_the_temperament() -> None:
    state = a_game()

    written = system_prompt(project(state, SEER), briefing=briefing())

    assert "loup-garou" in written.lower(), "the rules of the game"
    assert "voyante" in written.lower(), "the role this seat was dealt"
    assert A_PERSONALITY in written, "the temperament of D-058"


def test_the_system_prompt_disarms_anything_written_inside_a_block() -> None:
    """D-067: what a block holds is a claim, never an instruction."""
    written = system_prompt(project(a_game(), SEER), briefing=briefing())

    assert "<parole>" in written
    assert "instruction" in written.lower()


def test_the_system_prompt_frames_lying_as_a_rule_of_the_game() -> None:
    """The countermeasure to a model that will not lie, and denounces itself (BS-001)."""
    written = system_prompt(project(a_game(), WOLF), briefing=briefing())

    assert "mensonge" in written.lower() or "mentir" in written.lower()


def test_a_wolf_is_told_who_its_pack_is_and_a_villager_is_not() -> None:
    """The one thing a role knows about somebody else's (D-032)."""
    state = a_game()

    assert "Émile" in system_prompt(project(state, WOLF), briefing=briefing())
    assert "Émile" not in system_prompt(project(state, VILLAGER), briefing=briefing())


# --- The prompt holds nothing the view does not (J7.2.6, GL-3) --------------


def transcript_of(state: GameState, viewer: PlayerId) -> tuple[str, str, str]:
    """The three prompts a seat would be handed in that state."""
    journal = project_journal(Journal().events, Recipient.of(state.player(viewer)))
    view = project(state, viewer)
    return (
        system_prompt(view, briefing=briefing()),
        turn_prompt(view, journal=journal),
        bid_prompt(view, journal=journal),
    )


@pytest.mark.parametrize("viewer", [SEER, WOLF, VILLAGER], ids=["seer", "wolf", "villager"])
def test_a_secret_nobody_is_entitled_to_changes_nothing_in_their_prompts(viewer: PlayerId) -> None:
    """Whole prompts compared, so a leak under any wording makes them differ.

    The same reason the projections of J3 are compared whole rather than field by
    field: a test looking for one name would be blind to a leak worded any other
    way.
    """
    as_a_hunter = transcript_of(a_game(other_role=RoleName.HUNTER), viewer)
    as_a_witch = transcript_of(a_game(other_role=RoleName.WITCH), viewer)

    assert as_a_hunter == as_a_witch


def test_the_player_whose_role_changed_does_see_the_difference() -> None:
    """Guard the test above: prompts identical for everybody would pass it too."""
    as_a_hunter = transcript_of(a_game(other_role=RoleName.HUNTER), OTHER)
    as_a_witch = transcript_of(a_game(other_role=RoleName.WITCH), OTHER)

    assert as_a_hunter != as_a_witch


# --- The prompts live in files (J7.2.1) --------------------------------------


def python_modules() -> list[pathlib.Path]:
    return sorted(pathlib.Path(lupus_ex_machina.llm.__file__).parent.rglob("*.py"))


def prose_in(module: pathlib.Path) -> list[str]:
    """Every long string literal in a module, docstrings aside."""
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    docstrings = {
        ast.get_docstring(node, clean=False)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and len(node.value) > 120
        and node.value not in docstrings
    ]


def test_no_prompt_is_written_in_the_code() -> None:
    """They are rewritten constantly while calibrating; that must not touch code."""
    offenders = {module.name: prose_in(module) for module in python_modules() if prose_in(module)}

    assert offenders == {}


def test_the_guard_actually_reads_the_modules() -> None:
    """Guard the guard: an empty scan would make the test above vacuous."""
    assert len(python_modules()) > 5
