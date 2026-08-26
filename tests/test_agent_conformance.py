"""What being an agent means, asked of every adapter there is.

Each of these is defensible for an agent that is not the one that happens to
be written: it states something a run relies on, not something an adapter
happens to do. Which environment variable carries the model, which file the
configuration lives in, which tool is the one with nothing here to run it —
all of that stays in that adapter's own file.

Two things an agent owes are beside this rather than in it: what it writes for
itself and what it refuses to write over, in `tests/test_agent_configuration.py`;
and what a run could send off this machine, in `tests/test_agent_leaving.py`
with a file per subject beside it, `tests/test_agent_hosted_tools.py` and
`tests/test_agent_transcript_sharing.py`; and where it keeps a conversation it
started, in `tests/test_agent_conversations.py`. An adapter is done when all of
them pass. `tests/agents_under_test.py` is where a second one joins, and it is the
only edit to the suite that adding one takes.

`tmp_path` is where offgrid keeps what it writes for the length of one test,
which is what lets these say what was written without knowing which files any
adapter uses.
"""

import subprocess
from pathlib import Path

import pytest

from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.launch import Launch
from tests.agent_conformance import (
    EVERY_AGENT,
    WANTED,
    plan_for_a_model,
    read_everything_under,
)
from tests.agents_under_test import AgentUnderTest

pytestmark = EVERY_AGENT


def test_what_an_agent_speaks_is_readable_before_anything_is_written(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # `run` refuses a runtime and an agent that cannot talk to each other
    # before it loads anything, which is only worth doing while asking costs
    # nothing and touches nothing.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)

    assert isinstance(agent.dialect, Dialect)
    assert read_everything_under(tmp_path) == {}


def test_an_agent_states_the_smallest_window_it_can_start_in(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # An agent whose system prompt and tool definitions do not fit in the
    # window fails at startup, after a load nobody gets the seconds back for.
    # Nothing in the domain can learn that number, so the agent states it, and
    # asking costs nothing and touches nothing.
    #
    # It is what the agent needs rather than what anyone prefers, so what a
    # person typed does not move it: an argument that did would buy a failed
    # launch after a load that had already been paid for. That half is a guard
    # rather than a slice — an adapter settling its floor at binding time
    # cannot read an argument — and it is here for the adapter that parses its
    # passthrough and could.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)
    told = agent_under_test.prepare(
        monkeypatch, tmp_path, passthrough=("--context-floor", "1")
    )

    assert agent.context_floor > 0
    assert told.context_floor == agent.context_floor
    assert read_everything_under(tmp_path) == {}


def test_an_agent_names_the_command_that_would_be_run(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # Whether the agent is on this machine is a `PATH` lookup, and a lookup
    # needs the name to look up. It cannot be derived from the adapter's own
    # name — `claude-code` runs `claude` — and reading it off a launch would
    # mean building one, which takes a model nothing has yet.
    #
    # A bare name rather than a path, because a path is where it is on the
    # machine it was written on, and looking one up on `PATH` is the only
    # answer about this machine.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)

    assert agent.command
    assert Path(agent.command).name == agent.command, (
        f"{agent.command} is a path rather than a command to look up"
    )
    # What is looked up is what runs, so an adapter cannot name one command
    # and start another.
    assert plan_for_a_model(agent).argv[0] == agent.command


def test_planning_a_launch_writes_nothing(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # Agents configure themselves in ways that have nothing in common, and
    # that belongs where a caller can see it happen rather than smuggled into
    # the call that builds an argument list.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)
    agent.configure()
    configured = read_everything_under(tmp_path)

    plan_for_a_model(agent)

    assert read_everything_under(tmp_path) == configured


def test_a_launch_can_be_shown_rather_than_started(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # An environment and an argument list, so that what will run can be
    # printed, checked or refused while it is still only a plan.
    #
    # Both ways of starting something, because the suite otherwise lets one of
    # them through: `tests/conftest.py` refuses the runtime's own tool and runs
    # anything else for real.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)
    for starting in ("Popen", "run"):
        monkeypatch.setattr(
            subprocess,
            starting,
            lambda *args, **kwargs: pytest.fail("planning a launch started something"),
        )

    launch = plan_for_a_model(agent)

    assert isinstance(launch, Launch)
    assert all(isinstance(value, str) for value in launch.env.values())
    assert launch.argv and all(isinstance(argument, str) for argument in launch.argv)
    # What a person is owed before it starts travels with it, so an agent that
    # will do something they would otherwise meet mid-session says so where
    # the launch can still be shown rather than run.
    assert launch.caution is None or launch.caution.strip()


def test_the_model_that_will_answer_reaches_the_launch(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # The model is the one thing a run discovers, and `plan` writes nothing, so
    # a launch that does not carry it is one that answers from whatever the
    # agent was pointed at last. As a setting of its own or inside an argument,
    # since an agent naming it `--model=` carries it just as well.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)

    launch = plan_for_a_model(agent)

    assert any(WANTED in said for said in [*launch.env.values(), *launch.argv])


def test_arguments_typed_by_a_person_reach_the_launch(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # Handed on unchanged and in the order they were typed: an agent reading
    # the last of two of the same argument gets a different answer if they are
    # reordered, and a prompt is not the same prompt rearranged.
    typed = ("-p", "say something")
    agent = agent_under_test.prepare(monkeypatch, tmp_path, passthrough=typed)

    argv = plan_for_a_model(agent).argv

    runs = [tuple(argv[at : at + len(typed)]) for at in range(len(argv))]

    assert typed in runs, f"{typed} is not in {argv} as it was typed"


def test_where_the_runtime_listens_reaches_the_agent(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # Through the launch for an agent that takes an address as a setting, or
    # through the configuration for one that writes it into a file of its own.
    # Which of the two is the adapter's business; that it happens is not.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)
    agent.configure()
    launch = plan_for_a_model(agent)

    written = read_everything_under(tmp_path).values()
    told = [
        *launch.env.values(),
        *launch.argv,
        *(held.decode(errors="replace") for held in written),
    ]

    assert any(agent_under_test.address in said for said in told)
