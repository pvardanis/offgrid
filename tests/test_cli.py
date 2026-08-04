import pytest
from typer.testing import CliRunner

from offgrid.cli import app
from offgrid.machine import Machine
from offgrid.model import Model

GIB = 1024**3
runner = CliRunner()


@pytest.fixture
def here(monkeypatch, tmp_path):
    """Answer with a fixed machine and a fixed catalogue, and write nowhere real."""
    machine = Machine(
        chip="Apple M1 Max", memory_bytes=64 * GIB, wired_limit_bytes=56 * GIB
    )
    monkeypatch.setattr("offgrid.cli.detect", lambda: machine)
    monkeypatch.setattr("offgrid.cli.DEFAULT_PATH", tmp_path / "profile.yaml")
    monkeypatch.setattr("offgrid.cli.CONFIG_DIR", tmp_path / "claude-code")
    monkeypatch.setattr("offgrid.cli.catalogue", lambda host: {"data": []})
    monkeypatch.setattr(
        "offgrid.cli.resident",
        lambda payload: Model(identifier="qwen/qwen3.6-35b-a3b", context_limit=212224),
    )
    return tmp_path


def test_setup_reports_the_machine(here):
    result = runner.invoke(app, ["setup"])
    assert result.exit_code == 0
    assert "Apple M1 Max" in result.stdout


def test_setup_says_what_size_of_model_fits(here):
    result = runner.invoke(app, ["setup"])
    assert "4-bit" in result.stdout
    assert "parameters" in result.stdout


def test_setup_names_no_model(here):
    # Choosing one is a manual step; offgrid states the budget, not the answer.
    result = runner.invoke(app, ["setup"])
    assert "qwen" not in result.stdout


def test_setup_writes_a_profile_that_can_be_read_back(here):
    from offgrid.profile import load

    runner.invoke(app, ["setup"])
    assert load(here / "profile.yaml").chip == "Apple M1 Max"


def test_doctor_needs_a_profile_first(here):
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "offgrid setup" in result.stdout


def test_doctor_reports_the_model_that_would_answer(here):
    runner.invoke(app, ["setup"])
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "qwen/qwen3.6-35b-a3b" in result.stdout


def test_doctor_says_when_the_runtime_holds_nothing(here, monkeypatch):
    runner.invoke(app, ["setup"])
    monkeypatch.setattr("offgrid.cli.resident", lambda payload: None)

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "no model" in result.stdout.lower()


def test_run_launches_the_agent_with_the_resident_model(here, monkeypatch):
    runner.invoke(app, ["setup"])
    started = {}
    monkeypatch.setattr(
        "offgrid.cli.start",
        lambda launch: started.update(env=launch.env, argv=launch.argv),
    )

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    assert started["env"]["ANTHROPIC_MODEL"] == "qwen/qwen3.6-35b-a3b"
    assert started["argv"][0] == "claude"


def test_run_passes_the_rest_of_the_line_to_the_agent(here, monkeypatch):
    runner.invoke(app, ["setup"])
    started = {}
    monkeypatch.setattr(
        "offgrid.cli.start", lambda launch: started.update(argv=launch.argv)
    )

    runner.invoke(app, ["run", "--", "-p", "hello"])
    assert started["argv"][-2:] == ["-p", "hello"]


def test_run_refuses_when_nothing_is_loaded(here, monkeypatch):
    runner.invoke(app, ["setup"])
    monkeypatch.setattr("offgrid.cli.resident", lambda payload: None)

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 1
    assert "load a model" in result.stdout.lower()
