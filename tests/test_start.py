"""What starting the agent does: the environment it gets, and how it stops."""

import signal
import subprocess

import pytest

from offgrid.launch import STOPS, Launch, start

LAUNCH = Launch(env={"ANTHROPIC_BASE_URL": "http://127.0.0.1:1234"}, argv=["claude"])


class _Agent:
    """A process that is not started, answering as one that was."""

    def __init__(
        self,
        code: int = 0,
        watching: dict | None = None,
        listening_for: int = signal.SIGTERM,
    ):
        self.code = code
        self.watching = watching if watching is not None else {}
        self.listening_for = listening_for

    def wait(self) -> int:
        self.watching["handler"] = signal.getsignal(self.listening_for)
        return self.code

    def terminate(self) -> None:
        self.watching["terminated"] = True


def _agent(monkeypatch: pytest.MonkeyPatch, agent: _Agent) -> dict:
    """Answer for the agent's process, recording how it was started."""
    started: dict = {}

    def popen(argv, env=None, **kwargs):
        started["argv"] = list(argv)
        started["env"] = env
        return agent

    monkeypatch.setattr(subprocess, "Popen", popen)

    return started


def test_the_agent_is_pointed_at_the_local_runtime(monkeypatch):
    # The privacy guarantee lives here: an agent started without this
    # environment reaches Anthropic's servers on the caller's own key.
    started = _agent(monkeypatch, _Agent())

    start(LAUNCH)

    assert started["argv"] == ["claude"]
    assert started["env"]["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:1234"


def test_the_agent_keeps_the_rest_of_the_callers_environment(monkeypatch):
    monkeypatch.setenv("EXAMPLE_FROM_THE_CALLER", "kept")
    started = _agent(monkeypatch, _Agent())

    start(LAUNCH)

    assert started["env"]["EXAMPLE_FROM_THE_CALLER"] == "kept"


def test_the_agents_exit_code_comes_back(monkeypatch):
    _agent(monkeypatch, _Agent(code=3))

    assert start(LAUNCH) == 3


def test_an_agent_killed_by_a_signal_reports_it_as_a_shell_would(monkeypatch):
    _agent(monkeypatch, _Agent(code=-signal.SIGTERM))

    assert start(LAUNCH) == 128 + signal.SIGTERM


@pytest.mark.parametrize("number", STOPS)
def test_a_stop_signal_reaches_the_agent(monkeypatch, number):
    # Being stopped without passing it on leaves the agent running against a
    # model offgrid is about to let go of.
    watching: dict = {}
    _agent(monkeypatch, _Agent(watching=watching, listening_for=number))

    start(LAUNCH)
    watching["handler"](number, None)

    assert watching["terminated"] is True


def test_the_callers_signal_handling_is_put_back(monkeypatch):
    before = signal.getsignal(signal.SIGTERM)
    _agent(monkeypatch, _Agent())

    start(LAUNCH)

    assert signal.getsignal(signal.SIGTERM) is before
