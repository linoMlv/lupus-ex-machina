"""Playing a game from the console.

The command is the human-facing proof of J2: a full game runs, with scripted
agents, no model and no server.
"""

import pytest

from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.play import ROLE_LABELS, main


def test_a_game_is_played_and_reported(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--seed", "1"])

    printed = capsys.readouterr().out
    assert exit_code == 0
    assert "Nuit 0" in printed
    assert "Jour 1" in printed
    assert "Victoire" in printed


def test_the_same_seed_prints_the_same_game(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--seed", "12"])
    first = capsys.readouterr().out

    main(["--seed", "12"])
    second = capsys.readouterr().out

    assert first == second


def test_the_table_size_is_configurable(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--seed", "3", "--players", "6"])

    assert "6 joueurs" in capsys.readouterr().out


def test_an_unsupported_table_size_fails_without_a_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["--players", "12"])

    assert exit_code == 1
    assert "6 à 8" in capsys.readouterr().err


def test_the_roles_are_revealed_only_once_the_game_is_over(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["--seed", "5"])
    printed = capsys.readouterr().out

    assert printed.index("Victoire") < printed.index("loup-garou")


def test_every_role_the_engine_knows_can_be_named() -> None:
    """A role without a label would only break once the game is over."""
    assert set(ROLE_LABELS) == set(RoleName)
