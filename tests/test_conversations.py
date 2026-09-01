"""What offgrid refuses to say about where a conversation is kept.

The conformance suite asks each adapter what it answers. These ask what the
value refuses to be built from, including the answers no adapter gives today: a
directory that depends on where the person reading is standing, and a place
with no way back into it. Both are faults in an adapter rather than in a
machine, so both raise at construction, the way `Reading` does one file over.
That reaches a person as a traceback rather than as one of offgrid's own
sentences, because `reporting()` catches `OffgridError` alone — which is the
right audience for an adapter that is wrong, and is why the messages are
written to whoever is writing one.

Each guard was proven by taking it out and watching the test here go red.
"""

from pathlib import Path

import pytest

from offgrid.domain.running.conversations import Conversations

RESUMED_BY = "`offgrid run -- --resume` opens a picker over these."


def test_a_relative_directory_is_refused_saying_why():
    # `doctor` prints this for somebody to go and look at, and a relative path
    # names a different directory depending on where they are standing when
    # they read it.
    with pytest.raises(ValueError) as refused:
        Conversations(kept_in=Path("claude-code"), resume_with=RESUMED_BY)

    assert "relative" in str(refused.value)


def test_a_place_with_no_way_back_into_it_is_refused_saying_why():
    # A directory on its own is what a person already had: the whole finding is
    # that a conversation started here is not where the agent looks on its own,
    # and the command is the half that acts on it.
    with pytest.raises(ValueError) as refused:
        Conversations(kept_in=Path("/opt/offgrid/opencode/store"), resume_with="  ")

    assert "names the command that opens one" in str(refused.value)
