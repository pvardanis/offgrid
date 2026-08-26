"""What a run derives for OpenCode, and what it is started with.

What any agent owes is stated in `tests/test_agent_conformance.py`, and hosted
tools beside it. What offgrid writes into the directory OpenCode keeps is in
`tests/test_opencode_configuring.py`. What is here is the other half of that
split: everything offgrid derives, which is rebuilt every run so that none of
it can go stale.
"""

import pytest

from offgrid.agents.opencode import prepare
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.leaving import Status, Subject
from tests.agent_conformance import read_about
from tests.doubles import StandInAgentConfig
from tests.opencode_bindings import (
    HOST,
    RUNTIME_SPELLINGS,
    SETTINGS,
    STORE,
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


def test_the_floor_opencode_states_is_the_placeholder_it_says_it_is(agent):
    # Not a claim that OpenCode fails below 25,000: that number was measured
    # against Claude Code, and the evidence points the other way here. What is
    # pinned is that the placeholder has not quietly become a fact — the
    # source says it is a guess, so this asserts the guess rather than a
    # window anybody watched OpenCode refuse. Issue #153 is the measurement,
    # and settling it is meant to change this test.
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


def test_a_model_whose_window_is_unstated_carries_no_limit_at_all(agent):
    # Nothing to size it to and nothing to guess with. Measured on opencode
    # 1.18.20, a `limit` naming an output cap and no context is refused as an
    # invalid configuration before a token is generated, so the cap goes with
    # the window rather than outliving it.
    derived = read_derived(plan_for(agent, window=None))

    assert derived["provider"]["offgrid"]["models"][WANTED] == {}


def test_the_file_the_agent_keeps_is_the_one_it_is_pointed_at(launch, tmp_path):
    # The variable is written out rather than imported, because a launch that
    # named it something else would carry the durable half where OpenCode
    # never looks — and importing the constant would rename both sides at once.
    assert launch.env["OPENCODE_CONFIG"] == str(tmp_path / "opencode" / SETTINGS)


def test_the_conversations_a_run_leaves_behind_are_kept_where_offgrid_put_them(
    launch, tmp_path
):
    # The other half of an installation. Pointing OpenCode at a configuration
    # file settles what it is configured with and nothing about where it writes
    # what a session leaves behind, so a run answering through a provider that
    # exists only inside it would otherwise land in a person's own store,
    # beside the providers they authenticated themselves.
    #
    # The variable is written out rather than imported for the same reason the
    # one above it is: renaming both sides at once would leave the store where
    # OpenCode never moved it.
    # Named and then not dropped, because a launch takes what it drops back
    # out after the two environments are merged: dropping this one would leave
    # the store where a person's own OpenCode keeps it, which is the whole of
    # what this is for.
    assert launch.env["XDG_DATA_HOME"] == str(tmp_path / "opencode" / STORE)
    assert "XDG_DATA_HOME" not in launch.dropped


def test_the_command_line_carries_only_what_a_person_typed(agent):
    # Which model answers is a key in the configuration, so offgrid adds no
    # argument of its own — and a person's own model flag beats it the same
    # way it beats the Claude Code adapter's environment. One shape covers the
    # interactive interface and a one-shot run alike.
    typed = ("run", "say something")

    argv = plan_for(bind(passthrough=typed)).argv

    assert argv == ["opencode", *typed]


def test_nothing_the_launch_carries_names_a_runtime(launch):
    # The criterion is stated over the adapter, not over what `configure`
    # writes, so the half a run derives is asked the same question: nothing
    # in this adapter knows a runtime has a name.
    carried = read_everything_carried(launch).lower()

    assert not [spelling for spelling in RUNTIME_SPELLINGS if spelling in carried]


def test_a_config_built_for_another_agent_cannot_reach_this_one(agent):
    # Both registry dicts are typed on the base config, so nothing but this
    # refusal stops a name being bound to one adapter's config and another's
    # factory. Asked of this adapter because `test_architecture.py` asks it
    # of the Claude Code adapter alone.
    with pytest.raises(TypeError, match="OpenCodeConfig was expected"):
        prepare(StandInAgentConfig(runtime_host=HOST), ())


def test_opencode_offers_no_hosted_tool_and_says_what_that_was_measured_on(agent):
    # The case the reading was designed for: an agent with nothing hosted
    # says something true and dated rather than implementing a guard whose
    # body does nothing.
    found = read_about(agent, Subject.HOSTED_TOOLS)

    assert found.status is Status.NONE_OFFERED
    assert "1.18.20" in found.detail
