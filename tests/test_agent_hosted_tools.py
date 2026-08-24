"""What every adapter owes about the tools offgrid cannot run for it.

These are why the guard is a named member at all. A `read_hosted_tools` whose
body answers `DENIED` and looks at nothing satisfies the Protocol and the type
checker both, and this is what says so.

An agent offering nothing hosted cannot be put into a state where one is
reachable, so the two that ask about that state skip. What the skip costs is
the test between them: an adapter claiming that has to answer `NONE_OFFERED`
and say what it measured, which is what `docs/decisions.md` means by a dated
fact with evidence behind it — and what `doctor` prints.

Be straight about what that price does not buy. An adapter reading nothing and
returning the answer whole still passes, because for an agent with genuinely
nothing hosted no configuration exists that would make a correct reading answer
differently. What is caught is the claim made wrongly: an adapter that does
offer a hosted tool and says otherwise answers something else and goes red. The
rest of it rests on the evidence being readable by a person.

That test is a regression guard rather than a slice while `AGENTS_UNDER_TEST`
holds only adapters that offer one: it skips, and starts running the day an
adapter claims the property.

`tmp_path` is where offgrid keeps what it writes for the length of one test,
which is what lets these say what was written without knowing which files any
adapter uses.
"""

from pathlib import Path

import pytest

from offgrid.domain.running.hosted_tools import (
    HostedToolsStatus,
    require_hosted_tools_denied,
)
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


def test_an_agent_offering_no_hosted_tool_says_so_with_its_evidence(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # What the two skips below cost. An adapter is allowed to say it has
    # nothing hosted, and saying it silences the two tests that put an agent
    # into a state where one is reachable — so the claim is asked for here
    # instead, off a configuration the adapter has written.
    #
    # The evidence beside it is the half a person can check: `doctor` prints
    # that line, so an adapter answering with nothing to say puts a blank one
    # in the report where the version it measured belongs.
    if not agent_under_test.offers_no_hosted_tool:
        pytest.skip(f"{agent_under_test.name} offers a hosted tool")
    agent = agent_under_test.prepare(monkeypatch, tmp_path)

    agent.configure()

    found = agent.read_hosted_tools()
    assert found.status is HostedToolsStatus.NONE_OFFERED
    assert found.detail.strip()


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
    if agent_under_test.offers_no_hosted_tool:
        pytest.skip(f"{agent_under_test.name} has no hosted tool to permit")
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
    if agent_under_test.offers_no_hosted_tool:
        pytest.skip(f"{agent_under_test.name} has no hosted tool to permit")
    agent_under_test.write_a_configuration_permitting_a_hosted_tool(tmp_path)
    agent = agent_under_test.prepare(monkeypatch, tmp_path)
    permitting = read_everything_under(tmp_path)

    agent.configure()

    after = read_everything_under(tmp_path)
    assert {name: after[name] for name in permitting} == permitting
    with pytest.raises(HostedToolReachableError):
        require_hosted_tools_denied(agent.read_hosted_tools())
