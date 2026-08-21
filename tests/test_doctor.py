"""What `offgrid doctor` reports about the runtime, the model and the agent.

The seam is the command: the lines a person reads, and the exit code a script
reads beside them. What it says about the tools an agent can reach is its own
module.
"""

import httpx
from typer.testing import CliRunner

from offgrid.cli import app
from tests.doubles import StandInAgent, answer_as_an_agent, serve_get
from tests.lmstudio_server import RESIDENT
from tests.profiles import add_to_section

runner = CliRunner()


def test_doctor_needs_a_profile_first(here):
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "offgrid setup" in result.stderr


def test_doctor_reports_the_runtime_the_profile_names(here):
    # Which runtime answers is the profile's to say, and `doctor` is where
    # someone checks what a run will do before making one.
    runner.invoke(app, ["setup"])

    result = runner.invoke(app, ["doctor"])

    assert "lmstudio" in result.stderr


def test_doctor_refuses_a_key_the_agent_it_names_does_not_read(here):
    # The section belongs to whichever adapter its name picks, so the registry
    # is where a typo under `agent:` is caught. It is caught before anything is
    # asked of the runtime, and it names the section as well as the key.
    runner.invoke(app, ["setup"])
    add_to_section(here, "agent", theme="dark")

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "`agent` section" in result.stderr
    assert "theme" in result.stderr
    assert "claude-code" in result.stderr


def test_doctor_refuses_a_key_the_runtime_it_names_does_not_read(here):
    runner.invoke(app, ["setup"])
    add_to_section(here, "runtime", timeout=30)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "`runtime` section" in result.stderr
    assert "timeout" in result.stderr
    assert "lmstudio" in result.stderr


def test_doctor_reports_the_agent_the_profile_names_and_what_it_speaks(here):
    # What a run would launch, and the dialect the pairing turns on.
    runner.invoke(app, ["setup"])

    result = runner.invoke(app, ["doctor"])

    assert "claude-code" in result.stderr
    assert "anthropic" in result.stderr


def test_doctor_reports_the_model_that_would_answer(here):
    runner.invoke(app, ["setup"])
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert RESIDENT in result.stderr


def test_doctor_prints_what_the_model_could_serve_and_what_it_is_served_at(here):
    # Two different statements, and one number cannot make both: the ceiling
    # is a capability the model has whether or not anything holds it, and the
    # window is what it is being served at now.
    runner.invoke(app, ["setup"])

    result = runner.invoke(app, ["doctor"])

    assert "ceiling   262144" in result.stderr
    assert "window    212224" in result.stderr


def test_doctor_prints_the_window_the_agent_needs_to_start(here, monkeypatch):
    # The agent's own number, asked of the agent: a second adapter that starts
    # in a window Claude Code cannot would otherwise be reported as Claude
    # Code's.
    from offgrid.domain.running.dialect import Dialect

    answer_as_an_agent(
        monkeypatch, StandInAgent(dialect=Dialect.ANTHROPIC, context_floor=9000)
    )
    runner.invoke(app, ["setup"])

    result = runner.invoke(app, ["doctor"])

    assert "floor     9000" in result.stderr


def test_doctor_refuses_a_runtime_that_will_not_answer_rather_than_reporting_one(
    here, monkeypatch
):
    # The reading that used to be one answer is two, and only one of them is
    # a state of the runtime. Read as the other, the report's first line calls
    # a runtime reachable that nothing answered for.
    runner.invoke(app, ["setup"])

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    serve_get(monkeypatch, refuse)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "No model server answered at http://127.0.0.1:1234" in result.stderr
    assert "reachable" not in result.stderr
    assert "nothing held" not in result.stderr
