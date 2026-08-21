"""The words offgrid prints for what somebody else did or did not state.

Not one of the agreed seams, because the case that matters cannot be reached
from any of them: a `Model` carrying a zero takes a payload no live runtime
has been seen to send, and fixtures here are captured rather than invented.
The function takes the value directly, which is the one door a zero fits
through.
"""

import pytest

from offgrid.shared.wording import describe_what_was_stated


def test_nothing_stated_is_said_as_unstated():
    assert describe_what_was_stated(None) == "unstated"


@pytest.mark.parametrize("stated", [262144, 1, "Apache 2.0"])
def test_what_was_stated_is_said_as_itself(stated):
    assert describe_what_was_stated(stated) == str(stated)


def test_a_zero_is_a_number_somebody_stated():
    # The whole of why this is a function. A `Model` and a `Listing` are
    # parsed from someone else's answer and refuse nothing, so falsiness here
    # reports a number that arrived as one that never came — and a ceiling of
    # zero is refused every window by `refuse_a_window_above_the_ceiling`
    # while the report beside it says nothing was stated.
    assert describe_what_was_stated(0) == "0"


def test_an_empty_string_is_a_licence_somebody_published():
    # The same rule on the other type: a published licence of "" is a row the
    # table filled in, and `unstated` is what offgrid says about a row it did
    # not.
    assert describe_what_was_stated("") == ""
