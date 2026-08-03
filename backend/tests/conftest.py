"""Shared fixtures.

The suite must produce the same result on every machine. Settings are read from
``LUPUS_*`` variables and from a ``.env`` file next to the project (see
config.py), so a developer who follows `.env.example` and creates one would
otherwise change what the tests assert — silently, and only on their machine.
"""

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Cut every test off from the ambient configuration.

    Ambient ``LUPUS_*`` variables are dropped, and the working directory is moved
    somewhere empty so no ``.env`` is ever picked up. A test that wants a setting
    sets it itself, which is also what makes it readable.
    """
    for name in list(os.environ):
        if name.startswith("LUPUS_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
