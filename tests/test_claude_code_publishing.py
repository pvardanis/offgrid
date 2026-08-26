"""Which arguments Claude Code takes for a session that runs somewhere else.

The conformance suite asks that a run which could publish is stopped, and it
types one argument to arrange that. What is here is every argument the adapter
claims to read and both spellings each is typed in — deleting either flag from
`CLOUD_ARGUMENTS`, or the joined spelling from the match, left that suite green.

The negative cases matter as much: the match is anchored at the start of an
argument, and a reading that took any mention of the flag for the flag would
refuse every run that asks Claude Code about it.
"""

import pytest

from offgrid.agents.claude_code.publishing import (
    CLOUD_ARGUMENTS,
    read_transcript_sharing,
)
from offgrid.domain.running.leaving import Status

ASKING = [
    *((flag,) for flag in CLOUD_ARGUMENTS),
    *((f"{flag}=whatever",) for flag in CLOUD_ARGUMENTS),
    ("--print", "fix the bug", CLOUD_ARGUMENTS[0]),
]


@pytest.mark.parametrize("passthrough", ASKING, ids=lambda p: " ".join(p))
def test_every_argument_that_opens_a_cloud_session_stops_a_run(passthrough):
    # Driven off the constant, so an argument added to it without a reading is
    # covered the day it is added rather than the day somebody remembers.
    found = read_transcript_sharing(passthrough)

    assert found.status is Status.PERMITTED
    assert found.remedy.strip()


@pytest.mark.parametrize(
    "passthrough",
    [
        (),
        ("--print", "what does --cloud do?"),
        ("--cloudy",),
        ("--environmental",),
        ("--print", "--cloud is the flag I mean"),
    ],
    ids=["nothing", "quoted", "longer", "longer too", "mid-prompt"],
)
def test_an_argument_that_only_mentions_one_does_not_stop_a_run(passthrough):
    # A person asking Claude Code about the flag is not asking for a cloud
    # session, and refusing them would make offgrid unusable for the question.
    assert read_transcript_sharing(passthrough).status is Status.DENIED


def test_the_refusal_names_the_argument_that_caused_it():
    # Only the adapter knows which argument to drop, so a refusal that does
    # not name it is a wall with no door in it.
    found = read_transcript_sharing(("--environment", "ccpool_1"))

    assert "--environment" in found.detail
    assert "Drop the argument" in found.remedy


def test_what_is_said_when_nothing_asks_claims_no_more_than_was_measured():
    # Three other arguments touch a session elsewhere and none was measured,
    # so the sentence names the two that were rather than claiming the line is
    # clear. Issue #167 is the measurement.
    said = read_transcript_sharing(()).detail

    for flag in CLOUD_ARGUMENTS:
        assert flag in said
    assert "cloud session" in said
