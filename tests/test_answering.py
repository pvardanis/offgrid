"""Which model answers, and which error a caller importing offgrid gets.

The command line covers what a person sees, and the adapter covers what
reaching a state costs. What is left here is the domain's own question: the
model that answers is the one asked for, or the one already held, and a
runtime holding nothing is not a runtime that could not be reached.

The runtime is a real connection with the server stood in for, not a fake
satisfying the port: a fake would answer whatever this file told it to, which
is not evidence about anything.
"""

import pytest
from pydantic import ValidationError

from offgrid.domain.running.answering import get_resident_model, hold_model
from offgrid.domain.running.model import ModelRequest
from offgrid.runtimes.lmstudio import connect
from offgrid.runtimes.lmstudio.config import LMStudioConfig
from offgrid.shared.exceptions import ModelUnavailableError
from tests.lmstudio_server import answer_as_lm_studio

HOST = "127.0.0.1:1234"
RESIDENT = "a/held-7b"


def test_a_runtime_holding_nothing_is_not_a_runtime_that_is_unreachable(monkeypatch):
    # The difference decides where someone looks next, so it is carried by
    # the type and not only by the wording.
    answer_as_lm_studio(monkeypatch, cold={"a/cold-7b": 8192})

    with pytest.raises(ModelUnavailableError, match="holding no model"):
        get_resident_model(connect(LMStudioConfig(host=HOST)))


def test_the_model_that_would_answer_is_the_one_being_held(monkeypatch):
    answer_as_lm_studio(monkeypatch, holding={RESIDENT: 8192}, cold={"a/cold-7b": 8192})

    assert get_resident_model(connect(LMStudioConfig(host=HOST))).identifier == RESIDENT


def test_naming_no_model_answers_with_the_one_already_there(monkeypatch):
    # A run names a model or it does not, and where it does not the resident
    # one answers: no load, and the prefix cached against it survives. The
    # rule is the domain's rather than the command line's.
    asked = answer_as_lm_studio(
        monkeypatch, holding={RESIDENT: 8192}, cold={"a/other-7b": 8192}
    )

    model = hold_model(connect(LMStudioConfig(host=HOST)), ModelRequest())

    assert model.identifier == RESIDENT
    assert asked["loaded"] is None
    assert asked["let_go"] == []


def test_a_window_asked_for_without_a_model_holds_the_resident_one_at_it(
    monkeypatch,
):
    # Naming a window and no model is asking for what is already answering,
    # at a size. Reading it as "no model named, so nothing to do" would hand
    # back the old window while the person believes they asked for a new one.
    asked = answer_as_lm_studio(monkeypatch, holding={RESIDENT: 8192})

    model = hold_model(
        connect(LMStudioConfig(host=HOST)), ModelRequest(context_window=16000)
    )

    assert model.identifier == RESIDENT
    assert model.context_window == 16000
    assert asked["window"] == 16000


def test_naming_neither_a_model_nor_a_window_costs_no_load(monkeypatch):
    asked = answer_as_lm_studio(monkeypatch, holding={RESIDENT: 8192})

    model = hold_model(connect(LMStudioConfig(host=HOST)), ModelRequest())

    assert model.context_window == 8192
    assert asked["loaded"] is None
    assert asked["let_go"] == []


def test_the_model_asked_for_is_held_alone(monkeypatch):
    asked = answer_as_lm_studio(
        monkeypatch, holding={RESIDENT: 8192}, cold={"a/other-7b": 32768}
    )

    model = hold_model(
        connect(LMStudioConfig(host=HOST)), ModelRequest(identifier="a/other-7b")
    )

    assert model.identifier == "a/other-7b"
    assert model.context_window == 32768
    assert asked["let_go"] == [RESIDENT]


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
