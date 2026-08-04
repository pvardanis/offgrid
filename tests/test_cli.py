import pytest
from typer.testing import CliRunner

from offgrid.cli import app
from offgrid.machine import Machine

GIB = 1024**3
CEILING = 262144
RESIDENT = "qwen/qwen3.6-35b-a3b"
runner = CliRunner()


def _entry(identifier: str, *, served: int, ceiling: int, in_memory: bool) -> dict:
    """Describe one model the way LM Studio's catalogue does."""
    entry = {
        "id": identifier,
        "type": "llm",
        "state": "loaded" if in_memory else "not-loaded",
        "max_context_length": ceiling,
    }
    if in_memory:
        entry["loaded_context_length"] = served

    return entry


def _runtime(monkeypatch, *, holding=None, cold=None, ceiling=CEILING) -> dict:
    """Stand in for the model server, answering as what it holds changes.

    Each mapping is a model against the context it is served at. A cold model
    states only its ceiling until something loads it, which is what makes the
    difference between the two numbers visible.

    :return: What the runtime was asked to load and let go of.
    """
    served = {**(holding or {}), **(cold or {})}
    in_memory = dict.fromkeys(holding or {}, True) | dict.fromkeys(cold or {}, False)
    asked: dict = {"loaded": None, "let_go": []}

    def catalogue(host: str) -> dict:
        return {
            "data": [
                _entry(name, served=served[name], ceiling=ceiling, in_memory=held)
                for name, held in in_memory.items()
            ]
        }

    def load(host: str, identifier: str, **kwargs) -> None:
        in_memory[identifier] = True
        asked["loaded"] = identifier

    def unload(identifier: str) -> None:
        in_memory[identifier] = False
        asked["let_go"].append(identifier)

    monkeypatch.setattr("offgrid.cli.catalogue", catalogue)
    monkeypatch.setattr("offgrid.cli.load_model", load)
    monkeypatch.setattr("offgrid.cli.unload", unload)

    return asked


def _launched(monkeypatch, code: int = 0) -> dict:
    """Record what would have been started, without starting it."""
    seen: dict = {}
    monkeypatch.setattr(
        "offgrid.cli.start",
        lambda launch: seen.update(env=launch.env, argv=launch.argv) or code,
    )

    return seen


@pytest.fixture
def runtime(monkeypatch):
    """A model server holding one model, served below its ceiling."""
    return _runtime(monkeypatch, holding={RESIDENT: 212224})


@pytest.fixture
def here(monkeypatch, tmp_path, runtime):
    """Answer with a fixed machine, and write nowhere real."""
    machine = Machine(
        chip="Apple M1 Max", memory_bytes=64 * GIB, wired_limit_bytes=56 * GIB
    )
    monkeypatch.setattr("offgrid.cli.detect", lambda: machine)
    monkeypatch.setattr("offgrid.cli.DEFAULT_PATH", tmp_path / "profile.yaml")
    monkeypatch.setattr("offgrid.cli.CONFIG_DIR", tmp_path / "claude-code")
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
    assert RESIDENT in result.stdout


def test_doctor_says_when_the_runtime_holds_nothing(here, monkeypatch):
    runner.invoke(app, ["setup"])
    _runtime(monkeypatch, cold={"a/cold-7b": 8192})

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "no model" in result.stdout.lower()


def test_run_launches_the_agent_with_the_resident_model(here, monkeypatch):
    runner.invoke(app, ["setup"])
    started = _launched(monkeypatch)

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    assert started["env"]["ANTHROPIC_MODEL"] == RESIDENT
    assert started["argv"][0] == "claude"


def test_run_passes_the_rest_of_the_line_to_the_agent(here, monkeypatch):
    runner.invoke(app, ["setup"])
    started = _launched(monkeypatch)

    runner.invoke(app, ["run", "--", "-p", "hello"])
    assert started["argv"][-2:] == ["-p", "hello"]


def test_run_refuses_when_nothing_is_loaded(here, monkeypatch):
    runner.invoke(app, ["setup"])
    _runtime(monkeypatch, cold={"a/cold-7b": 8192})

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 1
    assert "load a model" in result.stdout.lower()


def test_run_loads_a_named_model_that_is_not_resident(here, monkeypatch):
    runner.invoke(app, ["setup"])
    asked = _runtime(monkeypatch, holding={RESIDENT: 212224}, cold={"a/other-7b": 8192})
    _launched(monkeypatch)

    result = runner.invoke(app, ["run", "--model", "a/other-7b"])
    assert result.exit_code == 0
    assert asked["loaded"] == "a/other-7b"


def test_a_resident_model_is_not_loaded_again(here, monkeypatch, runtime):
    # Asking for what is already held costs nothing: no wait for weights, and
    # the prefix cached against it survives.
    runner.invoke(app, ["setup"])
    _launched(monkeypatch)

    result = runner.invoke(app, ["run", "--model", RESIDENT])
    assert result.exit_code == 0
    assert runtime["loaded"] is None


def test_swapping_models_says_what_it_costs(here, monkeypatch):
    runner.invoke(app, ["setup"])
    _runtime(monkeypatch, holding={RESIDENT: 212224}, cold={"a/other-7b": 8192})
    _launched(monkeypatch)

    result = runner.invoke(app, ["run", "--model", "a/other-7b"])
    assert result.exit_code == 0
    assert "cached prefix" in result.stdout


def test_a_model_the_runtime_does_not_have_is_refused(here, monkeypatch):
    runner.invoke(app, ["setup"])
    _launched(monkeypatch)

    result = runner.invoke(app, ["run", "--model", "a/absent-7b"])
    assert result.exit_code == 1
    assert "a/absent-7b" in result.stdout


def test_run_lets_go_of_models_it_did_not_ask_for(here, monkeypatch):
    runner.invoke(app, ["setup"])
    asked = _runtime(monkeypatch, holding={RESIDENT: 212224}, cold={"a/other-7b": 8192})
    _launched(monkeypatch)

    runner.invoke(app, ["run", "--model", "a/other-7b"])
    assert RESIDENT in asked["let_go"]


def test_the_model_is_let_go_when_the_agent_finishes(here, monkeypatch, runtime):
    runner.invoke(app, ["setup"])
    _launched(monkeypatch)

    runner.invoke(app, ["run"])
    assert runtime["let_go"][-1] == RESIDENT


def test_the_agents_exit_code_is_offgrids_own(here, monkeypatch):
    runner.invoke(app, ["setup"])
    _launched(monkeypatch, code=3)

    assert runner.invoke(app, ["run"]).exit_code == 3


def test_the_model_is_let_go_even_when_the_agent_is_interrupted(
    here, monkeypatch, runtime
):
    runner.invoke(app, ["setup"])

    def interrupted(launch):
        raise KeyboardInterrupt

    monkeypatch.setattr("offgrid.cli.start", interrupted)

    runner.invoke(app, ["run"])
    assert runtime["let_go"] == [RESIDENT]


def test_a_runtime_that_will_not_let_go_is_reported_not_hidden(here, monkeypatch):
    from offgrid.exceptions import RuntimeUnreachableError

    runner.invoke(app, ["setup"])

    def refuse(name):
        raise RuntimeUnreachableError("lms would not unload it")

    monkeypatch.setattr("offgrid.cli.unload", refuse)
    _launched(monkeypatch)

    result = runner.invoke(app, ["run"])
    assert "still holding" in result.stdout


def test_the_profile_names_the_model_when_the_command_line_does_not(here, monkeypatch):
    runner.invoke(app, ["setup"])
    _name_in_profile(here, "a/other-7b")
    asked = _runtime(monkeypatch, holding={RESIDENT: 212224}, cold={"a/other-7b": 8192})
    _launched(monkeypatch)

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    assert asked["loaded"] == "a/other-7b"


def test_compaction_is_sized_from_what_the_runtime_serves(here, monkeypatch):
    # A model that was not loaded yet states only its ceiling. LM Studio
    # serves a smaller window than that, and compacting against the ceiling
    # means never compacting: the server truncates the prefix instead.
    runner.invoke(app, ["setup"])
    _runtime(monkeypatch, cold={"a/big-7b": 32768}, ceiling=262144)
    started = _launched(monkeypatch)

    runner.invoke(app, ["run", "-m", "a/big-7b"])
    assert started["env"]["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] == "32768"


def test_the_command_line_beats_the_profile(here, monkeypatch):
    runner.invoke(app, ["setup"])
    _name_in_profile(here, "a/from-profile-7b")
    asked = _runtime(
        monkeypatch, cold={"a/from-profile-7b": 8192, "a/asked-for-7b": 8192}
    )
    started = _launched(monkeypatch)

    runner.invoke(app, ["run", "-m", "a/asked-for-7b"])
    assert asked["loaded"] == "a/asked-for-7b"
    assert started["env"]["ANTHROPIC_MODEL"] == "a/asked-for-7b"


def _name_in_profile(here, identifier: str) -> None:
    """Write a model into the stored profile, as a person editing it would."""
    path = here / "profile.yaml"
    path.write_text(path.read_text() + f"model: {identifier}\n")
