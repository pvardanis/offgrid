"""What every adapter owes about a transcript of this run leaving the machine.

The gap issue #162 is about, asked of every adapter rather than of the one it
was found in. `docs/decisions.md` promises no transcript leaves this machine,
and for one agent that promise was written into a file once and never read
again — so a person who edited the file, or who typed an argument that
publishes the session, got a run that went ahead and said nothing.

This is the half `configure` cannot cover. A file offgrid wrote and a person
then edited is a file `configure` leaves alone, deliberately, so the reading is
the only thing left that can tell them what the edit costs — and it has to name
what to change, since nothing else will write it now.

Neither state has one shape, which is why the stand-in arranges it: for one
agent it is a key in a JSON file, for another an argument on the command line.
"""

from pathlib import Path

import pytest

from offgrid.domain.running.leaving import Status, Subject, require_nothing_leaves
from offgrid.shared.exceptions import CouldLeaveThisMachineError
from tests.agent_conformance import EVERY_AGENT, read_about, read_everything_under
from tests.agents_under_test import AgentUnderTest

pytestmark = EVERY_AGENT


def test_a_run_that_could_publish_a_transcript_is_stopped(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # What a person reads has to be actable on: only the adapter knows which
    # key to set or which argument to drop, so a refusal carrying neither is a
    # wall with no door in it.
    passthrough = agent_under_test.arrange_a_transcript_that_leaves(tmp_path)
    agent = agent_under_test.prepare(monkeypatch, tmp_path, passthrough=passthrough)

    agent.configure()

    # The message is asserted whole rather than by substring, so it says which
    # subject stopped the run: a substring check would pass on a refusal about
    # some other subject that happened to quote the same words.
    found = read_about(agent, Subject.TRANSCRIPT_SHARING)

    with pytest.raises(CouldLeaveThisMachineError) as refused:
        require_nothing_leaves(agent.read_what_leaves_this_machine())

    assert str(refused.value) == f"{Subject.TRANSCRIPT_SHARING}: {found.said}"
    assert found.detail and found.remedy


def test_what_could_publish_a_transcript_is_not_written_over(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # The same split the hosted-tool reading rests on. Writing the key back
    # would answer a deliberate edit with a run that quietly disagrees with
    # the file, and the guard could never report it again.
    #
    # An agent whose sharing lives on the command line has no file to write
    # over, and comparing an empty directory against itself would pass while
    # asserting nothing — the vacuity #155 was filed about. So it skips, and
    # what the skip costs is the two tests either side, which do run for it.
    passthrough = agent_under_test.arrange_a_transcript_that_leaves(tmp_path)
    arranged = read_everything_under(tmp_path)
    if not arranged:
        pytest.skip(f"{agent_under_test.name} shares through an argument, not a file")
    agent = agent_under_test.prepare(monkeypatch, tmp_path, passthrough=passthrough)

    agent.configure()

    after = read_everything_under(tmp_path)
    assert {name: after[name] for name in arranged} == arranged


def test_what_an_agent_writes_for_itself_settles_sharing(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # A machine that has run `offgrid setup` and nothing else is the ordinary
    # one, and on it the answer is settled rather than merely not refused: an
    # adapter that left this unwritten would refuse every first run.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)

    agent.configure()

    found = read_about(agent, Subject.TRANSCRIPT_SHARING)
    assert found.status in (Status.NONE_OFFERED, Status.DENIED)
    assert found.detail.strip()
