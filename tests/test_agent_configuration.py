"""What an agent writes for itself and keeps, asked of every adapter there is.

`configure` has one file to decide about at a time and three answers for it:
write where there is no edit to lose, keep what a person set, and refuse what
is neither. The first two are here; what it refuses rather than guess about is
beside this, in `tests/test_agent_configuration_refused.py`.

What it does not do is merge a key back into a file that parses. A file that
parses is a file a person edited, and the key likeliest to be missing from one
is the key that decides something offgrid promises — sharing off for OpenCode,
WebSearch denied for Claude Code. Putting those back silently would trade a
refusal a person can act on for a run that quietly disagrees with their file,
which is what `read_what_leaves_this_machine` exists to prevent.

`tmp_path` is where offgrid keeps what it writes for the length of one test,
which is what lets these say what was written without knowing which files any
adapter uses.
"""

from pathlib import Path

import pytest

from tests.agent_conformance import EVERY_AGENT, read_everything_under
from tests.agents_under_test import AgentUnderTest

pytestmark = EVERY_AGENT


def test_what_an_agent_needs_and_does_not_have_is_written(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    agent = agent_under_test.prepare(monkeypatch, tmp_path)

    agent.configure()

    assert read_everything_under(tmp_path) != {}


def test_what_a_person_edited_is_left_as_they_left_it(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # A configuration is meant to be edited, and a run is no place to lose
    # those edits. Every file the agent writes, because which of them a person
    # is allowed to keep is not the adapter's to choose.
    #
    # The adapter makes the edit, because an edit a person could plausibly have
    # made is one its own agent could still read: a file offgrid leaves alone
    # is one the agent goes on to load, so bytes that are an edit to nothing
    # would ask the suite to promise something no adapter should keep.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)
    agent.configure()
    agent_under_test.edit_the_configuration(tmp_path)
    edited = read_everything_under(tmp_path)

    agent.configure()

    assert read_everything_under(tmp_path) == edited


def test_a_configuration_emptied_is_written_again(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # An empty file holds no edit to lose, so what the agent cannot act on is
    # written into it rather than left there: a `configure` deciding by
    # existence alone leaves a file somebody truncated exactly as useless as it
    # found it, and says nothing about that either.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)
    agent.configure()
    written = read_everything_under(tmp_path)

    # Emptied and cut down to whitespace alike: an editor saving over a file
    # leaves the first, a person deleting its contents leaves the second, and
    # neither is anything anybody chose.
    for left_holding in (b"", b"\n   \n"):
        for name in written:
            (tmp_path / name).write_bytes(left_holding)

        agent.configure()

        assert read_everything_under(tmp_path) == written


def test_a_configuration_linked_to_a_file_that_is_there_is_followed(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # Pointing a configuration somewhere else is a thing people do on purpose,
    # so a link with a file at the far end is read through rather than
    # replaced. The refusal beside this one is about a link with nothing at the
    # far end, and a guard that could not tell them apart would take this away.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)
    agent.configure()
    written = read_everything_under(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    for name, held in written.items():
        linked = tmp_path / name
        target = elsewhere / linked.name
        target.write_bytes(held)
        linked.unlink()
        linked.symlink_to(target)
    followed = read_everything_under(tmp_path)

    agent.configure()

    assert read_everything_under(tmp_path) == followed
    assert all((tmp_path / name).is_symlink() for name in written)
