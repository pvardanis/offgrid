"""What every adapter owes about the reading as a whole.

What it answers about each way off this machine is asked in
`tests/test_agent_hosted_tools.py` and
`tests/test_agent_transcript_sharing.py`. This file asks the two things true of
the reading whichever subject it is about: that every one of them is answered,
and that what an adapter writes for itself passes its own guard.

`tmp_path` is where offgrid keeps what it writes for the length of one test,
which is what lets these say what was written without knowing which files any
adapter uses.
"""

from pathlib import Path

import pytest

from offgrid.domain.running.leaving import Subject, require_nothing_leaves
from tests.agent_conformance import EVERY_AGENT
from tests.agents_under_test import AgentUnderTest

pytestmark = EVERY_AGENT


def test_every_agent_answers_about_every_way_off_this_machine(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # A subject nobody answered is the failure the slot exists to prevent, one
    # level up: `run` would ask, get a tuple back, refuse nothing and start.
    # An adapter that has no such thing still owes the reading, so a subject
    # added later goes red on every adapter rather than on none.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)

    agent.configure()

    answered = [reading.subject for reading in agent.read_what_leaves_this_machine()]
    assert sorted(answered) == sorted(Subject)


def test_what_an_agent_writes_for_itself_satisfies_its_own_guard(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # An adapter whose own default fails its own guard cannot be run at all,
    # and one whose guard passes a configuration it never wrote is not reading
    # anything.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)

    agent.configure()

    require_nothing_leaves(agent.read_what_leaves_this_machine())
