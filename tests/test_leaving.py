"""What offgrid decides out of what an agent said about leaving this machine.

The conformance suites ask each adapter what it answers. These ask what the
decision does with an answer, including the answers no adapter gives today —
an adapter that says nothing, and a reading nobody could act on. Both are
faults in an adapter rather than in a machine, so both raise where they are
built rather than where somebody reads a report.
"""

import pytest

from offgrid.domain.running.leaving import (
    Reading,
    Status,
    Subject,
    require_nothing_leaves,
)
from offgrid.shared.exceptions import CouldLeaveThisMachineError


def _settled(subject: Subject) -> Reading:
    """A reading that stops nothing, for the subject named.

    :param subject: Which way off the machine it is about.

    :return: A settled reading.
    """
    return Reading(
        subject=subject,
        status=Status.NONE_OFFERED,
        detail=f"nothing offers {subject} here.",
    )


def test_a_run_starts_when_every_subject_is_settled():
    require_nothing_leaves(tuple(_settled(subject) for subject in Subject))


def test_an_agent_that_says_nothing_at_all_stops_the_run():
    # The failure this module exists to prevent, committed by the thing meant
    # to prevent it: an empty answer refuses nothing and the agent starts.
    with pytest.raises(ValueError, match="once each"):
        require_nothing_leaves(())


def test_an_agent_that_drops_one_subject_stops_the_run():
    # A subject added later reaches an adapter that answers about the others
    # and nothing else. Saying so only in the suite leaves it true of the
    # suite rather than of a run.
    with pytest.raises(ValueError) as refused:
        require_nothing_leaves((_settled(Subject.HOSTED_TOOLS),))

    assert str(Subject.TRANSCRIPT_SHARING) in str(refused.value)


def test_an_agent_that_answers_one_subject_twice_stops_the_run():
    # Two readings and two subjects is not the same as one each: the second
    # answer about one subject is an answer missing about another.
    doubled = (_settled(Subject.HOSTED_TOOLS), _settled(Subject.HOSTED_TOOLS))

    with pytest.raises(ValueError, match="once each"):
        require_nothing_leaves(doubled)


def test_the_first_unsettled_subject_in_order_is_what_the_run_refuses_on():
    # A person is given one thing to fix rather than a list, and the same one
    # each run until they have: an order that moved with the adapter's would
    # send them to a different file every time.
    readings = tuple(
        Reading(
            subject=subject,
            status=Status.PERMITTED,
            detail=f"{subject} is reachable.",
            remedy=f"close {subject}.",
        )
        for subject in reversed(list(Subject))
    )

    with pytest.raises(CouldLeaveThisMachineError) as refused:
        require_nothing_leaves(readings)

    assert str(refused.value).startswith(f"{next(iter(Subject))}:")


def test_a_reading_that_stops_a_run_must_say_what_to_change():
    # A refusal carrying no remedy is a wall with no door in it, and the empty
    # default makes leaving one out the easy mistake.
    with pytest.raises(ValueError, match="nothing to change"):
        Reading(
            subject=Subject.TRANSCRIPT_SHARING,
            status=Status.PERMITTED,
            detail="a transcript can leave.",
        )


def test_a_reading_that_stops_nothing_needs_no_remedy():
    Reading(
        subject=Subject.HOSTED_TOOLS,
        status=Status.DENIED,
        detail="the settings deny it.",
    )


def test_a_reading_that_says_nothing_it_found_is_refused():
    # Every status is a claim, and `doctor` prints the evidence for it: a
    # reading with none puts a blank line in the report.
    with pytest.raises(ValueError, match="says nothing it found"):
        Reading(
            subject=Subject.HOSTED_TOOLS,
            status=Status.NONE_OFFERED,
            detail="   ",
        )
