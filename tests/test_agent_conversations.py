"""What every adapter owes about where it keeps a conversation it started.

`claude --resume <id>` typed in an ordinary terminal answers "No conversation
found with session ID", for a session offgrid started minutes earlier. The
transcript is intact and where offgrid put it, and nothing said so.
`docs/decisions.md` says why the partition stays, under "A conversation started
here is resumed here"; this is what makes every adapter answer for it.

Neither half is one adapter's: an agent that kept its conversations in a
person's own directory would be one where a run's session shows up in the
picker of a run against a vendor's model, and one that named no way back in
would leave a person with a directory and no command.

`tmp_path` is where offgrid keeps what it writes for the length of one test,
which is what lets these say where a conversation lands without knowing which
directories any adapter uses.
"""

from pathlib import Path

import pytest

from tests.agent_conformance import (
    EVERY_AGENT,
    plan_for_a_model,
    read_everything_under,
)
from tests.agents_under_test import AgentUnderTest

pytestmark = EVERY_AGENT


def test_every_agent_keeps_a_conversation_inside_the_installation_offgrid_owns(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # The partition itself. An agent leaving its conversations where it keeps
    # them when a person starts it themselves puts a session that answered from
    # a model held here into the picker of a run against a vendor's model,
    # where resuming it silently changes which model answers.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)

    kept = agent.conversations

    assert kept.kept_in.is_relative_to(tmp_path), (
        f"{agent_under_test.name} keeps conversations at {kept.kept_in}, which is "
        f"outside the {tmp_path} offgrid runs it out of."
    )


def test_the_directory_reported_is_the_one_the_launch_points_the_agent_at(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # The two say the same thing twice, in two places, and nothing but
    # this holds them together: an adapter whose launch moved and whose reading
    # did not hands a person a confident path with nothing at the end of it,
    # which is worse than the silence it replaced.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)

    kept = agent.conversations
    launch = plan_for_a_model(agent)

    assert str(kept.kept_in) in launch.env.values(), (
        f"{agent_under_test.name} reports {kept.kept_in} and points the agent at "
        f"{sorted(launch.env.values())}, so the report names a directory no run "
        "writes into."
    )


def test_every_agent_says_how_to_get_back_into_one(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # A directory on its own is what a person already had. What they are
    # missing is the command, and it goes through offgrid for every adapter:
    # the store is reached by what a run sets, so the agent started on its own
    # reads a different one.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)

    kept = agent.conversations

    assert "offgrid run" in kept.resume_with, (
        f"{agent_under_test.name} says to resume with `{kept.resume_with}`, which "
        "does not go through a run, and only a run points the agent at the store."
    )


def test_asking_where_conversations_are_kept_writes_nothing(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # `doctor` asks this on a machine that has never run the agent, and a
    # report that created the directory it reports would answer its own
    # question.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)

    kept = agent.conversations

    # The directory itself as well as what is in it: an adapter that made the
    # store on its way past would leave nothing `read_everything_under` can
    # see, since that walks files, and the report would have answered its own
    # question.
    assert not kept.kept_in.exists()
    assert read_everything_under(tmp_path) == {}
