"""What a run and a report do with a profile naming OpenCode.

The seam is the command: what a person reads, and what gets launched. What the
adapter answers on its own is in `tests/test_opencode.py`; what every adapter
owes is in the conformance suites. What is here is the pair working end to end
— that naming `opencode` in the file is the whole of switching agents.

`tests/test_cli.py` asks the same of the Claude Code adapter, and this is its
own module so that neither grows past the length a file is kept to.
"""

import json

from typer.testing import CliRunner

from offgrid.cli import app
from offgrid.cli.binding import read_profile
from offgrid.domain.running.agent import AgentName
from tests.launches import record_launch
from tests.lmstudio_server import RESIDENT, answer_as_lm_studio
from tests.opencode_bindings import NAMED, name_opencode
from tests.profiles import add_to_section

runner = CliRunner()


def _derived(started):
    """Read what the run settled, out of the environment the agent was given."""
    return json.loads(started["env"]["OPENCODE_CONFIG_CONTENT"])


def test_a_profile_naming_opencode_binds_it(here):
    # Switching agents is one line in a hand-edited file.
    name_opencode(here)

    assert read_profile(here / "profile.yaml").agent.name is AgentName.OPENCODE


def test_run_starts_opencode_against_the_model_being_held(here, monkeypatch):
    name_opencode(here)
    asked = answer_as_lm_studio(monkeypatch, holding={RESIDENT: 212224})
    started = record_launch(monkeypatch)

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 0
    assert started["argv"][0] == "opencode"
    assert _derived(started)["model"] == f"offgrid/{RESIDENT}"
    assert asked["let_go"] == [RESIDENT]


def test_run_tells_opencode_the_window_the_runtime_settled_on(here, monkeypatch):
    # The window rather than the model's ceiling, which is 262144 here.
    name_opencode(here)
    answer_as_lm_studio(monkeypatch, holding={RESIDENT: 212224})
    started = record_launch(monkeypatch)

    runner.invoke(app, ["run"])

    limit = _derived(started)["provider"]["offgrid"]["models"][RESIDENT]["limit"]
    assert limit["context"] == 212224
    assert limit["output"] == 8192


def test_run_lets_the_model_go_when_opencode_fails(here, monkeypatch):
    # One machine with one pool of memory: whatever happened, nothing is left
    # holding weights nothing is using.
    name_opencode(here)
    asked = answer_as_lm_studio(monkeypatch, holding={RESIDENT: 212224})
    record_launch(monkeypatch, code=3)

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 3
    assert asked["let_go"] == [RESIDENT]


def test_run_says_the_way_back_on_exit(here, monkeypatch):
    # OpenCode prints no resume hint of its own, so the exit line supplies the
    # missing one the same way it corrects Claude's.
    name_opencode(here)
    answer_as_lm_studio(monkeypatch, holding={RESIDENT: 212224})
    record_launch(monkeypatch)

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 0
    assert "offgrid run -- --continue" in result.stderr


def test_run_hands_the_rest_of_the_line_to_opencode(here, monkeypatch):
    # Unchanged and in the order they were typed, and a subcommand among them
    # works: OpenCode's own interface and a one-shot run take one argv shape.
    name_opencode(here)
    started = record_launch(monkeypatch)

    runner.invoke(app, ["run", "--", "run", "say something"])

    assert started["argv"] == ["opencode", "run", "say something"]


def test_run_refuses_a_key_opencode_does_not_read(here, monkeypatch):
    # Before the load, and the message names the section, the adapter and the
    # key — so a typo under `agent:` is reported rather than dropped.
    name_opencode(here)
    add_to_section(here, "agent", theme="dark")
    started = record_launch(monkeypatch)

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 1
    assert "`agent` section" in result.stderr
    assert "theme" in result.stderr
    assert NAMED in result.stderr
    assert not started


def test_doctor_reports_opencode_without_starting_anything(here, monkeypatch):
    # The same reading `run` would act on, had without a load or a launch.
    name_opencode(here)
    started = record_launch(monkeypatch)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert NAMED in result.stderr
    assert "openai" in result.stderr
    assert not started


def test_doctor_says_opencode_offers_nothing_hosted(here):
    # An agent with nothing hosted, and the evidence a person can check is
    # the half that makes the claim cost something.
    name_opencode(here)

    result = runner.invoke(app, ["doctor"])

    assert "none_offered" in result.stderr
    assert "1.18.20" in result.stderr
