"""What a run may ask the runtime to hold, and what is refused as it is read.

The request is the half of the pair a person writes — a command line today, a
profile next — so what it refuses is a typo reported rather than read as
"nothing wanted". What a runtime answers with is a `Model`, and covered where
that runtime's parsing is.
"""

import pytest
from pydantic import ValidationError

from offgrid.domain.running.model import ModelRequest


def test_a_window_of_nothing_is_refused_as_not_a_window():
    # Zero is not a small window. Typer refuses it on the command line, but a
    # profile and a caller embedding offgrid reach this by other doors.
    with pytest.raises(ValidationError, match="greater than 0"):
        ModelRequest(context_window=0)


def test_a_window_below_nothing_is_refused():
    with pytest.raises(ValidationError, match="greater than 0"):
        ModelRequest(context_window=-1)


def test_a_name_nobody_typed_is_not_the_same_as_no_name():
    # An unset variable reaching `--model` used to answer with the resident
    # model, where the runtime should have said it does not have that.
    with pytest.raises(ValidationError, match="at least 1 character"):
        ModelRequest(identifier="")


def test_a_key_the_request_does_not_name_is_refused():
    # It is written by hand once the profile carries one, so a typo has to be
    # reported rather than read as "no window wanted".
    with pytest.raises(ValidationError, match="context_windwo"):
        ModelRequest.model_validate({"context_windwo": 32768})


def test_a_request_naming_neither_is_what_a_bare_run_asks():
    asked = ModelRequest()

    assert asked.identifier is None
    assert asked.context_window is None
