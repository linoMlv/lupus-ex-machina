"""Playing a whole game with real models, from the console (J7, exit criterion 1).

The command is exercised against the fake provider: what is under test is the
wiring — settings read, table seated, game played, report printed — and not the
provider. A test that reached the network would cost money and fail on a train.
"""

from pathlib import Path

import pytest

from lupus_ex_machina.config import Settings
from lupus_ex_machina.configuration.system import SystemOptions
from lupus_ex_machina.engine.persistence import read_journal
from lupus_ex_machina.engine.replay import replay
from lupus_ex_machina.llm.answers import BidAnswer, ReflectionAnswer, TurnAnswer
from lupus_ex_machina.llm.fake import FakeCompletions
from lupus_ex_machina.llm.personalities import personalities
from lupus_ex_machina.llm.provider import configured_provider
from lupus_ex_machina.play_llm import main


def answering(schema: type, messages: object) -> str:
    """A plausible answer for each shape, with nothing but a thought in it."""
    if schema is BidAnswer:
        return BidAnswer(urgency=40, intention="Peut-être parler.").model_dump_json()
    if schema is ReflectionAnswer:
        return ReflectionAnswer(reasoning="Ce tour m'a appris peu.").model_dump_json()
    return TurnAnswer(reasoning="J'observe.").model_dump_json()


def test_it_says_what_is_missing_when_no_key_is_configured(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The one thing a user forgets, and it must not read as a crash (D-090)."""
    exit_code = main(["--players", "6"])

    assert exit_code == 1
    assert "LUPUS_LLM_API_KEY" in capsys.readouterr().err


def test_a_whole_game_is_played_and_reported(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(
        ["--players", "6", "--seed", "4", "--forced-designation"],
        completions=FakeCompletions(invent=answering),
    )

    printed = capsys.readouterr().out
    assert exit_code == 0
    assert "Victoire" in printed, "the game reached an end"
    assert "Appels aux modèles" in printed, "the budget of a game is reported (GL-7)"


def test_what_a_game_cost_in_calls_and_in_seconds_is_reported(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exit criterion 7 of J7: calls *and* latency, measured and written down.

    Both, and read off the provider that knows them (GL-7): a budget of calls
    with no time against it says nothing about whether a game is watchable, and
    a latency nobody prints is a measurement nobody makes.
    """
    main(
        ["--players", "6", "--seed", "4", "--forced-designation"],
        completions=FakeCompletions(invent=answering),
    )

    printed = capsys.readouterr().out
    assert "Appels aux modèles" in printed
    assert "secondes" in printed.lower(), "the time those calls took"


def test_the_table_it_deals_is_announced_with_its_temperaments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A spectator sees who plays with what, when the configuration allows it (D-064)."""
    main(
        ["--players", "6", "--seed", "4", "--forced-designation"],
        completions=FakeCompletions(invent=answering),
    )

    printed = capsys.readouterr().out
    assert "mistral-small-latest" in printed
    assert any(temperament.name in printed for temperament in personalities().values()), (
        "every seat is announced with the temperament it plays"
    )


def test_a_provider_is_built_from_the_settings_when_a_key_is_there() -> None:
    """Building a client reaches nobody, so this is testable without a network."""
    settings = Settings(llm_api_key="clef-de-test", llm_base_url="https://ailleurs.test/v1")

    assert configured_provider(settings, SystemOptions()) is not None


def test_no_provider_is_built_without_a_key() -> None:
    assert configured_provider(Settings(), SystemOptions()) is None


def test_a_finished_game_is_archived_where_the_configuration_asks(tmp_path: Path) -> None:
    """J8.0.3, D-093 — the setting existed and nothing honoured it either.

    Written once the game is over, which is what makes it an archive and not a
    resume: what it is for is reading back a game that was played against real
    models, long after the process that played it.
    """
    main(
        ["--players", "6", "--seed", "4", "--forced-designation", "--archive-to", str(tmp_path)],
        completions=FakeCompletions(invent=answering),
    )

    archived = list(tmp_path.glob("*.jsonl"))
    assert len(archived) == 1
    assert replay(read_journal(archived[0])).players, "and it reads back as the game it was"


def test_nothing_is_written_when_no_archive_is_asked_for(tmp_path: Path) -> None:
    """The default is in memory: a game must not litter a disk nobody pointed at."""
    main(
        ["--players", "6", "--seed", "4", "--forced-designation"],
        completions=FakeCompletions(invent=answering),
    )

    assert list(tmp_path.iterdir()) == []


def test_the_provider_waits_the_way_the_game_is_configured() -> None:
    """J8.0, D-092 — the derivation exists; this is what makes somebody call it.

    The defect it guards against is not a wrong value, it is a value nobody
    reads: `retries_for` could be perfectly correct and never invoked, which is
    precisely the state J7 was left in.
    """
    provider = configured_provider(
        Settings(llm_api_key="clef-de-test"),
        SystemOptions(backoff_first_delay_seconds=9.0),
    )

    assert provider is not None
    assert provider.retries.first_delay_seconds == 9.0
