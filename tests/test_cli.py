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


def test_run_loads_a_named_model_that_is_not_resident(here, monkeypatch):
    runner.invoke(app, ["setup"])
    loaded = {}
    monkeypatch.setattr(
        "offgrid.cli.load_model",
        lambda host, identifier, **kw: loaded.update(name=identifier),
    )
    monkeypatch.setattr("offgrid.cli.start", lambda launch: None)
    monkeypatch.setattr(
        "offgrid.cli.parse_models",
        lambda payload: [Model(identifier="a/other-7b", context_limit=8192)],
    )

    result = runner.invoke(app, ["run", "--model", "a/other-7b"])
    assert result.exit_code == 0
    assert loaded["name"] == "a/other-7b"


def test_a_resident_model_is_not_loaded_again(here, monkeypatch):
    runner.invoke(app, ["setup"])
    loaded = {}
    monkeypatch.setattr(
        "offgrid.cli.load_model", lambda *a, **k: loaded.update(called=True)
    )
    monkeypatch.setattr("offgrid.cli.start", lambda launch: None)

    runner.invoke(app, ["run", "--model", "qwen/qwen3.6-35b-a3b"])
    assert "called" not in loaded


def test_swapping_models_says_what_it_costs(here, monkeypatch):
    runner.invoke(app, ["setup"])
    monkeypatch.setattr("offgrid.cli.load_model", lambda *a, **k: None)
    monkeypatch.setattr("offgrid.cli.start", lambda launch: None)
    monkeypatch.setattr(
        "offgrid.cli.parse_models",
        lambda payload: [Model(identifier="a/other-7b", context_limit=8192)],
    )

    result = runner.invoke(app, ["run", "--model", "a/other-7b"])
    assert "cached prefix" in result.stdout


def test_a_model_the_runtime_does_not_have_is_refused(here, monkeypatch):
    runner.invoke(app, ["setup"])
    monkeypatch.setattr("offgrid.cli.parse_models", lambda payload: [])
    monkeypatch.setattr("offgrid.cli.start", lambda launch: None)

    result = runner.invoke(app, ["run", "--model", "a/absent-7b"])
    assert result.exit_code == 1
    assert "a/absent-7b" in result.stdout


def test_run_lets_go_of_models_it_did_not_ask_for(here, monkeypatch):
    runner.invoke(app, ["setup"])
    let_go = []
    monkeypatch.setattr("offgrid.cli.unload", lambda name: let_go.append(name))
    monkeypatch.setattr("offgrid.cli.load_model", lambda *a, **k: None)
    monkeypatch.setattr("offgrid.cli.start", lambda launch: 0)
    monkeypatch.setattr(
        "offgrid.cli.parse_models",
        lambda payload: [Model(identifier="a/other-7b", context_limit=8192)],
    )

    runner.invoke(app, ["run", "--model", "a/other-7b"])
    assert "qwen/qwen3.6-35b-a3b" in let_go


def test_the_model_is_let_go_when_the_agent_finishes(here, monkeypatch):
    runner.invoke(app, ["setup"])
    let_go = []
    monkeypatch.setattr("offgrid.cli.unload", lambda name: let_go.append(name))
    monkeypatch.setattr("offgrid.cli.start", lambda launch: 0)

    runner.invoke(app, ["run"])
    assert let_go[-1] == "qwen/qwen3.6-35b-a3b"


def test_the_agents_exit_code_is_offgrids_own(here, monkeypatch):
    runner.invoke(app, ["setup"])
    monkeypatch.setattr("offgrid.cli.unload", lambda name: None)
    monkeypatch.setattr("offgrid.cli.start", lambda launch: 3)

    assert runner.invoke(app, ["run"]).exit_code == 3


def test_the_model_is_let_go_even_when_the_agent_is_interrupted(here, monkeypatch):
    runner.invoke(app, ["setup"])
    let_go = []
    monkeypatch.setattr("offgrid.cli.unload", lambda name: let_go.append(name))

    def interrupted(launch):
        raise KeyboardInterrupt

    monkeypatch.setattr("offgrid.cli.start", interrupted)

    runner.invoke(app, ["run"])
    assert let_go == ["qwen/qwen3.6-35b-a3b"]


def test_a_runtime_that_will_not_let_go_is_reported_not_hidden(here, monkeypatch):
    from offgrid.exceptions import RuntimeUnreachableError

    runner.invoke(app, ["setup"])

    def refuse(name):
        raise RuntimeUnreachableError("lms would not unload it")

    monkeypatch.setattr("offgrid.cli.unload", refuse)
    monkeypatch.setattr("offgrid.cli.start", lambda launch: 0)

    result = runner.invoke(app, ["run"])
    assert "still holding" in result.stdout
