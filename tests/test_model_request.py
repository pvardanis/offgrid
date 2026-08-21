"""What a run may ask the runtime to hold, and what is refused as it is read.

The request is the half of the pair a person writes — a command line today, a
profile next — so what it refuses is a typo reported rather than read as
"nothing wanted". What a runtime answers with is a `Model`, and covered where
that runtime's parsing is.
"""

import pytest
from pydantic import ValidationError

from offgrid.domain.running.model import ModelRequest, read_what_was_typed
from offgrid.shared.exceptions import (
    ContextWindowUnworkableError,
    ModelUnavailableError,
)


def test_a_window_of_nothing_is_refused_as_not_a_window():
    # Zero is not a small window. Typer refuses it on the command line, but a
    # profile and a caller embedding offgrid reach this by other doors.
    with pytest.raises(ValidationError, match="greater than 0"):
        ModelRequest(context_window=0)


def test_a_window_below_nothing_is_refused():
    with pytest.raises(ValidationError, match="greater than 0"):
        ModelRequest(context_window=-1)


def test_a_name_nobody_typed_is_not_the_same_as_no_name():
    # An unset variable reaching `--model` arrives as an empty string. Read
    # as no name at all, it answers with the resident model where the runtime
    # should have said it does not have that.
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


def test_a_window_written_as_yes_is_not_a_window_of_one():
    # YAML reads `yes` as true, and a bool is an int to anything that does not
    # look: `gt=0` then passes it as 1, and the run is refused for a number
    # nobody wrote. `no` was refused all along, which is the worse asymmetry.
    with pytest.raises(ValidationError, match="not yes or no"):
        ModelRequest(context_window=True)


def test_a_name_that_is_only_spaces_is_a_name_nobody_typed():
    # `min_length` counts characters rather than content, so a space got a
    # sentence with a hole in it out of the runtime: does not have    .
    with pytest.raises(ValidationError, match="at least 1 character"):
        ModelRequest(identifier=" ")


def test_a_name_is_taken_without_what_was_typed_around_it():
    # A padded name is the model it names, and refusing it names a model that
    # looks identical to the one the runtime has.
    assert ModelRequest(identifier=" qwen/a-7b ").identifier == "qwen/a-7b"


def test_a_refusal_names_the_flag_the_value_was_typed_after():
    # One clause catches everything the request refuses, so a message naming
    # one flag is true only while the others cannot reach it — which is
    # typer's guarantee, made two layers away.
    with pytest.raises(ContextWindowUnworkableError, match="--context-window"):
        read_what_was_typed(identifier="a/one-7b", context_window=0)


def test_a_refused_name_says_what_was_typed_and_what_is_wrong_with_it():
    with pytest.raises(ModelUnavailableError) as refused:
        read_what_was_typed(identifier="", context_window=None)

    said = str(refused.value)
    assert "--model" in said
    assert "at least 1 character" in said
