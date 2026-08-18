"""What being an agent means, asked of every adapter there is.

Each of these is defensible for an agent that is not the one that happens to
be written: it states something a run relies on, not something an adapter
happens to do. Which environment variable carries the model, which file the
configuration lives in, which tool is the one with nothing here to run it —
all of that stays in that adapter's own file.

Two of these are why the guard is a named member at all. A `read_hosted_tools`
whose body answers `DENIED` and looks at nothing satisfies the Protocol and the
type checker both, and this is what says so.

An adapter is done when this passes. `tests/agents_under_test.py` is where a
second one joins, and it is the only edit to the suite that adding one takes.
"""

import subprocess
from pathlib import Path

import pytest

from offgrid.domain.running.agent import Agent
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.hosted_tools import require_hosted_tools_denied
from offgrid.domain.running.launch import Launch
from offgrid.domain.running.model import Model
from offgrid.shared.exceptions import HostedToolReachableError
from tests.agents_under_test import AGENTS_UNDER_TEST, AgentUnderTest

WANTED = "a/wanted-7b"
WINDOW = 32768
CEILING = 262144


@pytest.fixture(params=AGENTS_UNDER_TEST, ids=lambda under_test: under_test.name)
def agent_under_test(request: pytest.FixtureRequest) -> AgentUnderTest:
    """The adapter this run of the suite is asking about.

    :param request: The running test.

    :return: One adapter, and what standing its configuration in takes.
    """
    return request.param


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """Where offgrid keeps what it writes, for the length of one test.

    :param tmp_path: The directory pytest gives this test.

    :return: A home nothing outside the test can see.
    """
    return tmp_path


def _read_everything_under(home: Path) -> dict[str, bytes]:
    """Say what is on disk, so that two readings of it can be compared.

    Every file rather than the ones an adapter is known to write: a `configure`
    that leaves something extra behind is as much a change as one that rewrites
    a file, and no assertion naming files could see it.

    :param home: Where offgrid keeps what it writes for this run.

    :return: Each file under it, against what it holds.
    """
    return {
        str(path.relative_to(home)): path.read_bytes()
        for path in sorted(home.rglob("*"))
        if path.is_file()
    }


def _plan_for_a_model(agent: Agent) -> Launch:
    """Ask an agent how it would start against the model that will answer.

    :param agent: The adapter under test.

    :return: The environment and command it answered with.
    """
    return agent.plan(
        Model(identifier=WANTED, context_ceiling=CEILING, context_window=WINDOW)
    )


def test_what_an_agent_speaks_is_readable_before_anything_is_written(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, home: Path
):
    # `run` refuses a runtime and an agent that cannot talk to each other
    # before it loads anything, which is only worth doing while asking costs
    # nothing and touches nothing.
    agent = agent_under_test.prepare(monkeypatch, home)

    assert isinstance(agent.dialect, Dialect)
    assert _read_everything_under(home) == {}


def test_an_agent_states_the_smallest_window_it_can_start_in(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, home: Path
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
    agent = agent_under_test.prepare(monkeypatch, home)
    told = agent_under_test.prepare(
        monkeypatch, home, passthrough=("--context-floor", "1")
    )

    assert agent.context_floor > 0
    assert told.context_floor == agent.context_floor
    assert _read_everything_under(home) == {}


def test_what_an_agent_needs_and_does_not_have_is_written(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, home: Path
):
    agent = agent_under_test.prepare(monkeypatch, home)

    agent.configure()

    assert _read_everything_under(home) != {}


def test_what_a_person_edited_is_left_as_they_left_it(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, home: Path
):
    # A configuration is meant to be edited, and a run is no place to lose
    # those edits. Every file the agent writes, because which of them a person
    # is allowed to keep is not the adapter's to choose.
    agent = agent_under_test.prepare(monkeypatch, home)
    agent.configure()
    for name in _read_everything_under(home):
        (home / name).write_bytes(b"mine\n")
    edited = _read_everything_under(home)

    agent.configure()

    assert _read_everything_under(home) == edited


def test_what_an_agent_writes_for_itself_satisfies_its_own_guard(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, home: Path
):
    # An adapter whose own default fails its own guard cannot be run at all,
    # and one whose guard passes a configuration it never wrote is not reading
    # anything.
    agent = agent_under_test.prepare(monkeypatch, home)

    agent.configure()

    require_hosted_tools_denied(agent.read_hosted_tools())


def test_a_configuration_that_permits_a_hosted_tool_stops_a_run(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, home: Path
):
    # The failure this prevents is silent: a tool running on its vendor's
    # servers has nothing to run it against a model held here, so the model
    # emits the call as prose and the agent returns that as an answer.
    #
    # What a person reads is the adapter's own words and has to be actable on:
    # only the adapter knows which file to name or which argument to drop, so a
    # refusal carrying neither is a wall with no door in it.
    agent_under_test.write_a_configuration_permitting_a_hosted_tool(home)
    agent = agent_under_test.prepare(monkeypatch, home)
    found = agent.read_hosted_tools()

    with pytest.raises(HostedToolReachableError) as refused:
        require_hosted_tools_denied(found)

    said = str(refused.value)
    assert found.detail and found.detail in said
    assert found.remedy and found.remedy in said


def test_a_configuration_that_permits_a_hosted_tool_is_not_written_over(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, home: Path
):
    # Two jobs, and only one of them may stop a run. Writing over the edit
    # would turn a refusal a person can act on into a run that quietly does
    # something other than what their configuration says.
    agent_under_test.write_a_configuration_permitting_a_hosted_tool(home)
    agent = agent_under_test.prepare(monkeypatch, home)
    permitting = _read_everything_under(home)

    agent.configure()

    after = _read_everything_under(home)
    assert {name: after[name] for name in permitting} == permitting
    with pytest.raises(HostedToolReachableError):
        require_hosted_tools_denied(agent.read_hosted_tools())


def test_planning_a_launch_writes_nothing(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, home: Path
):
    # Agents configure themselves in ways that have nothing in common, and
    # that belongs where a caller can see it happen rather than smuggled into
    # the call that builds an argument list.
    agent = agent_under_test.prepare(monkeypatch, home)
    agent.configure()
    configured = _read_everything_under(home)

    _plan_for_a_model(agent)

    assert _read_everything_under(home) == configured


def test_a_launch_can_be_shown_rather_than_started(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, home: Path
):
    # An environment and an argument list, so that what will run can be
    # printed, checked or refused while it is still only a plan.
    #
    # Both ways of starting something, because the suite otherwise lets one of
    # them through: `tests/conftest.py` refuses the runtime's own tool and runs
    # anything else for real.
    agent = agent_under_test.prepare(monkeypatch, home)
    for starting in ("Popen", "run"):
        monkeypatch.setattr(
            subprocess,
            starting,
            lambda *args, **kwargs: pytest.fail("planning a launch started something"),
        )

    launch = _plan_for_a_model(agent)

    assert isinstance(launch, Launch)
    assert all(isinstance(value, str) for value in launch.env.values())
    assert launch.argv and all(isinstance(argument, str) for argument in launch.argv)


def test_the_model_that_will_answer_reaches_the_launch(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, home: Path
):
    # The model is the one thing a run discovers, and `plan` writes nothing, so
    # a launch that does not carry it is one that answers from whatever the
    # agent was pointed at last. As a setting of its own or inside an argument,
    # since an agent naming it `--model=` carries it just as well.
    agent = agent_under_test.prepare(monkeypatch, home)

    launch = _plan_for_a_model(agent)

    assert any(WANTED in said for said in [*launch.env.values(), *launch.argv])


def test_arguments_typed_by_a_person_reach_the_launch(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, home: Path
):
    # Handed on unchanged and in the order they were typed: an agent reading
    # the last of two of the same argument gets a different answer if they are
    # reordered, and a prompt is not the same prompt rearranged.
    typed = ("-p", "say something")
    agent = agent_under_test.prepare(monkeypatch, home, passthrough=typed)

    argv = _plan_for_a_model(agent).argv

    runs = [tuple(argv[at : at + len(typed)]) for at in range(len(argv))]

    assert typed in runs, f"{typed} is not in {argv} as it was typed"


def test_where_the_runtime_listens_reaches_the_agent(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, home: Path
):
    # Through the launch for an agent that takes an address as a setting, or
    # through the configuration for one that writes it into a file of its own.
    # Which of the two is the adapter's business; that it happens is not.
    agent = agent_under_test.prepare(monkeypatch, home)
    agent.configure()
    launch = _plan_for_a_model(agent)

    written = _read_everything_under(home).values()
    told = [
        *launch.env.values(),
        *launch.argv,
        *(held.decode(errors="replace") for held in written),
    ]

    assert any(agent_under_test.address in said for said in told)
