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

from offgrid.answering import get_resident, hold
from offgrid.exceptions import ModelUnavailableError
from offgrid.runtimes.lmstudio import connect
from tests.doubles import answer_as_lm_studio

HOST = "127.0.0.1:1234"
RESIDENT = "a/held-7b"


def test_a_runtime_holding_nothing_is_not_a_runtime_that_is_unreachable(monkeypatch):
    # The difference decides where someone looks next, so it is carried by
    # the type and not only by the wording.
    answer_as_lm_studio(monkeypatch, cold={"a/cold-7b": 8192})

    with pytest.raises(ModelUnavailableError, match="holding no model"):
        get_resident(connect(HOST))


def test_the_model_that_would_answer_is_the_one_being_held(monkeypatch):
    answer_as_lm_studio(monkeypatch, holding={RESIDENT: 8192}, cold={"a/cold-7b": 8192})

    assert get_resident(connect(HOST)).identifier == RESIDENT


def test_naming_no_model_answers_with_the_one_already_there(monkeypatch):
    # A run names a model or it does not, and where it does not the resident
    # one answers: no load, and the prefix cached against it survives. The
    # rule is the domain's rather than the command line's.
    asked = answer_as_lm_studio(
        monkeypatch, holding={RESIDENT: 8192}, cold={"a/other-7b": 8192}
    )

    model = hold(connect(HOST), None)

    assert model.identifier == RESIDENT
    assert asked["loaded"] is None
    assert asked["let_go"] == []


def test_the_model_asked_for_is_held_alone(monkeypatch):
    asked = answer_as_lm_studio(
        monkeypatch, holding={RESIDENT: 8192}, cold={"a/other-7b": 32768}
    )

    model = hold(connect(HOST), "a/other-7b")

    assert model.identifier == "a/other-7b"
    assert model.context_limit == 32768
    assert asked["let_go"] == [RESIDENT]
