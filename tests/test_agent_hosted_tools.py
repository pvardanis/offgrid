"""What every adapter owes about the tools offgrid cannot run for it.

These are why the guard is a named member at all. A `read_hosted_tools` whose
body answers `DENIED` and looks at nothing satisfies the Protocol and the type
checker both, and this is what says so.

`tmp_path` is where offgrid keeps what it writes for the length of one test,
which is what lets these say what was written without knowing which files any
adapter uses.
"""

from pathlib import Path

import pytest

from offgrid.domain.running.hosted_tools import require_hosted_tools_denied
from offgrid.shared.exceptions import HostedToolReachableError
from tests.agent_conformance import EVERY_AGENT, read_everything_under
from tests.agents_under_test import AgentUnderTest

pytestmark = EVERY_AGENT


def test_what_an_agent_writes_for_itself_satisfies_its_own_guard(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # An adapter whose own default fails its own guard cannot be run at all,
    # and one whose guard passes a configuration it never wrote is not reading
    # anything.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)

    agent.configure()

    require_hosted_tools_denied(agent.read_hosted_tools())


def test_a_configuration_that_permits_a_hosted_tool_stops_a_run(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # The failure this prevents is silent: a tool running on its vendor's
    # servers has nothing to run it against a model held here, so the model
    # emits the call as prose and the agent returns that as an answer.
    #
    # What a person reads is the adapter's own words and has to be actable on:
    # only the adapter knows which file to name or which argument to drop, so a
    # refusal carrying neither is a wall with no door in it.
    agent_under_test.write_a_configuration_permitting_a_hosted_tool(tmp_path)
    agent = agent_under_test.prepare(monkeypatch, tmp_path)
    found = agent.read_hosted_tools()

    with pytest.raises(HostedToolReachableError) as refused:
        require_hosted_tools_denied(found)

    said = str(refused.value)
    assert found.detail and found.detail in said
    assert found.remedy and found.remedy in said


def test_a_configuration_that_permits_a_hosted_tool_is_not_written_over(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # Two jobs, and only one of them may stop a run. Writing over the edit
    # would turn a refusal a person can act on into a run that quietly does
    # something other than what their configuration says.
    agent_under_test.write_a_configuration_permitting_a_hosted_tool(tmp_path)
    agent = agent_under_test.prepare(monkeypatch, tmp_path)
    permitting = read_everything_under(tmp_path)

    agent.configure()

    after = read_everything_under(tmp_path)
    assert {name: after[name] for name in permitting} == permitting
    with pytest.raises(HostedToolReachableError):
        require_hosted_tools_denied(agent.read_hosted_tools())
