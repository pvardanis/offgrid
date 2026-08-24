"""What a run derives for OpenCode, and what it is started with.

What any agent owes is stated in `tests/test_agent_conformance.py`, and hosted
tools beside it. What offgrid writes into the directory OpenCode keeps is in
`tests/test_opencode_configuring.py`. What is here is the other half of that
split: everything offgrid derives, which is rebuilt every run so that none of
it can go stale.
"""

import pytest

from offgrid.agents.opencode.launching import CONFIG_FILE
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.hosted_tools import HostedToolsStatus
from tests.opencode_bindings import (
    HOST,
    SETTINGS,
    WANTED,
    bind,
    plan_for,
    read_derived,
    read_everything_carried,
)


@pytest.fixture(autouse=True)
def _nowhere_real(monkeypatch, tmp_path):
    """Keep the directory an agent derives for itself inside the test."""
    monkeypatch.setattr("offgrid.domain.running.agent.OFFGRID_HOME", tmp_path)


@pytest.fixture
def agent():
    return bind()


@pytest.fixture
def launch(agent):
    return plan_for(agent)


def test_opencode_speaks_the_openai_dialect(agent):
    assert agent.dialect is Dialect.OPENAI


def test_opencode_will_not_start_in_a_window_under_25k(agent):
    # A placeholder measured against another agent rather than against this
    # one, and the constant says so. Written out here rather than read from
    # the source, so that changing it is a decision this test asks about —
    # including the one issue #153 exists to settle.
    assert agent.context_floor == 25_000


def test_the_agent_is_pointed_at_the_local_server(launch):
    options = read_derived(launch)["provider"]["offgrid"]["options"]

    assert options["baseURL"] == f"http://{HOST}/v1"


def test_an_address_changed_in_the_profile_is_the_one_the_next_run_uses(agent):
    # The address is derived, so it travels here rather than into the file:
    # `configure` never overwrites, so an address written once would be
    # silently wrong the moment the profile changed — and a stale one hangs
    # rather than erroring.
    moved = plan_for(bind(host="127.0.0.1:9999"))

    assert "9999" in read_derived(moved)["provider"]["offgrid"]["options"]["baseURL"]
    assert HOST not in read_everything_carried(moved)


def test_the_model_that_will_answer_is_named_under_its_provider(launch):
    # Measured on opencode 1.18.20: a provider entry carrying the package and
    # the address but no model list resolves no model at all, so naming the
    # provider is not enough to reach one.
    derived = read_derived(launch)

    assert derived["model"] == f"offgrid/{WANTED}"
    assert WANTED in derived["provider"]["offgrid"]["models"]


def test_the_window_the_runtime_settled_on_is_what_the_agent_is_told(launch):
    # The window rather than the ceiling: the ceiling is what the model could
    # be served at, and telling OpenCode that asks it to compact after the
    # runtime has already truncated the prefix.
    limit = read_derived(launch)["provider"]["offgrid"]["models"][WANTED]["limit"]

    assert limit["context"] == 32768
    assert limit["output"] == 8192


def test_a_model_whose_window_is_unstated_is_not_sized_from_its_ceiling(agent):
    # Nothing to size it to and nothing to guess with, so nothing is said
    # about context and the output cap still is.
    derived = read_derived(plan_for(agent, window=None))

    limit = derived["provider"]["offgrid"]["models"][WANTED]["limit"]
    assert "context" not in limit
    assert limit["output"] == 8192


def test_the_file_the_agent_keeps_is_the_one_it_is_pointed_at(launch, tmp_path):
    assert launch.env[CONFIG_FILE] == str(tmp_path / "opencode" / SETTINGS)


def test_the_command_line_carries_only_what_a_person_typed(agent):
    # Which model answers is a key in the configuration, so offgrid adds no
    # argument of its own — and a person's own model flag beats it the same
    # way it beats the other adapter's environment. One shape covers the
    # interactive interface and a one-shot run alike.
    typed = ("run", "say something")

    argv = plan_for(bind(passthrough=typed)).argv

    assert argv == ["opencode", *typed]


def test_opencode_offers_no_hosted_tool_and_says_what_that_was_measured_on(agent):
    # The first adapter to answer this, and the case the reading was designed
    # for: an agent with nothing hosted says something true and dated rather
    # than implementing a guard whose body does nothing.
    found = agent.read_hosted_tools()

    assert found.status is HostedToolsStatus.NONE_OFFERED
    assert "1.18.20" in found.detail
