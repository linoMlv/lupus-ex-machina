"""Architecture guards on the engine package.

The engine must stay playable, and testable, without a model and without a
network (D-001, GL-2). That is a property of the imports, so it is checked
mechanically rather than trusted: an accidental import is exactly the kind of
thing a reviewer stops noticing after a while.
"""

import ast
import pathlib

import lupus_ex_machina.engine

ENGINE_ROOT = pathlib.Path(lupus_ex_machina.engine.__file__).parent

# Anything that would drag a model, a network client or a web framework into the
# rules of the game.
FORBIDDEN_IMPORTS = frozenset(
    {
        "openai",
        "mistralai",
        "anthropic",
        "httpx",
        "httpx2",
        "requests",
        "aiohttp",
        "fastapi",
        "starlette",
        "uvicorn",
    }
)

# Reproducibility rests on a single seeded generator, so `random` belongs to one
# module only. A stray `random.choice` elsewhere silently breaks replay.
RANDOMNESS_OWNER = "rng.py"


def engine_modules() -> list[pathlib.Path]:
    return sorted(ENGINE_ROOT.rglob("*.py"))


def imported_roots(module: pathlib.Path) -> set[str]:
    """Return the top-level package of every import in a module."""
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    roots: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])

    return roots


def test_the_engine_imports_no_model_client_nor_web_framework() -> None:
    offenders = {
        module.name: sorted(imported_roots(module) & FORBIDDEN_IMPORTS)
        for module in engine_modules()
        if imported_roots(module) & FORBIDDEN_IMPORTS
    }

    assert offenders == {}


def test_randomness_lives_in_a_single_module() -> None:
    offenders = sorted(
        module.name
        for module in engine_modules()
        if "random" in imported_roots(module) and module.name != RANDOMNESS_OWNER
    )

    assert offenders == []


def test_the_guard_actually_inspects_the_engine() -> None:
    """Guard the guard: an empty scan would make both tests above vacuous."""
    modules = {module.name for module in engine_modules()}

    assert RANDOMNESS_OWNER in modules
    assert len(modules) > 5
