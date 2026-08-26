"""What offgrid refuses to say about where a conversation is kept.

The conformance suite asks each adapter what it answers. These ask what the
value refuses to be built from, including the answers no adapter gives today: a
directory that depends on where the person reading is standing, and a place
with no way back into it. Both are faults in an adapter rather than in a
machine, so both raise where the value is built rather than where somebody
reads a report.

This is a regression guard rather than a slice: each was checked by taking the
guard out and watching the test fail.
"""

from pathlib import Path

import pytest

from offgrid.domain.running.keeping import Conversations

RESUMED_BY = "`offgrid run -- --resume` opens a picker over these."


def test_a_directory_and_a_way_back_into_it_is_all_it_takes():
    kept = Conversations(
        kept_in=Path("/opt/offgrid/claude-code"), resumed_by=RESUMED_BY
    )

    assert kept.kept_in == Path("/opt/offgrid/claude-code")
    assert kept.resumed_by == RESUMED_BY


def test_a_relative_directory_is_refused_saying_why():
    # `doctor` prints this for somebody to go and look at, and a relative path
    # names a different directory depending on where they are standing when
    # they read it.
    with pytest.raises(ValueError) as refused:
        Conversations(kept_in=Path("claude-code"), resumed_by=RESUMED_BY)

    assert "relative" in str(refused.value)


def test_a_place_with_no_way_back_into_it_is_refused_saying_why():
    # A directory on its own is what a person already had: the whole finding is
    # that a conversation started here is not where the agent looks on its own,
    # and the command is the half that acts on it.
    with pytest.raises(ValueError) as refused:
        Conversations(kept_in=Path("/opt/offgrid/opencode/store"), resumed_by="  ")

    assert "how to open one" in str(refused.value)
