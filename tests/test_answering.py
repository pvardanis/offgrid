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

from offgrid.domain.running.answering import get_resident_model, hold_model
from offgrid.domain.running.model import ModelRequest
from offgrid.runtimes.lmstudio import connect
from offgrid.runtimes.lmstudio.config import LMStudioConfig
from offgrid.shared.exceptions import (
    ContextWindowUnworkableError,
    ModelUnavailableError,
)
from tests.lmstudio_server import answer_as_lm_studio

HOST = "127.0.0.1:1234"
RESIDENT = "a/held-7b"
# Low enough that the windows asked for below it clear it, so a test about
# something else is not also a test about the floor.
FLOOR = 4096


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

    model = hold_model(
        connect(LMStudioConfig(host=HOST)), ModelRequest(), context_floor=FLOOR
    )

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
        connect(LMStudioConfig(host=HOST)),
        ModelRequest(context_window=16000),
        context_floor=FLOOR,
    )

    assert model.identifier == RESIDENT
    assert model.context_window == 16000
    assert asked["window"] == 16000


def test_naming_neither_a_model_nor_a_window_costs_no_load(monkeypatch):
    asked = answer_as_lm_studio(monkeypatch, holding={RESIDENT: 8192})

    model = hold_model(
        connect(LMStudioConfig(host=HOST)), ModelRequest(), context_floor=FLOOR
    )

    assert model.context_window == 8192
    assert asked["loaded"] is None
    assert asked["let_go"] == []


def test_the_model_asked_for_is_held_alone(monkeypatch):
    asked = answer_as_lm_studio(
        monkeypatch, holding={RESIDENT: 8192}, cold={"a/other-7b": 32768}
    )

    model = hold_model(
        connect(LMStudioConfig(host=HOST)),
        ModelRequest(identifier="a/other-7b"),
        context_floor=FLOOR,
    )

    assert model.identifier == "a/other-7b"
    assert model.context_window == 32768
    assert asked["let_go"] == [RESIDENT]


def test_a_window_below_the_agents_floor_is_refused_before_any_load(monkeypatch):
    # The agent's system prompt and tool definitions do not fit below its
    # floor, so it fails at startup — after a load costing tens of seconds
    # nobody gets back. Both numbers are named, so the next one to type is in
    # the message rather than in the source.
    asked = answer_as_lm_studio(monkeypatch, holding={RESIDENT: 8192})

    with pytest.raises(ContextWindowUnworkableError, match="8000") as raised:
        hold_model(
            connect(LMStudioConfig(host=HOST)),
            ModelRequest(context_window=8000),
            context_floor=25_000,
        )

    assert "25000" in str(raised.value)
    assert asked["order"] == []


def test_a_window_above_the_models_ceiling_is_refused_before_any_load(monkeypatch):
    # The runtime takes this one without complaint and serves the impossible
    # number back, so nobody downstream can tell it is not real. offgrid
    # refuses it on the person's behalf, and names what the model does state.
    asked = answer_as_lm_studio(
        monkeypatch, cold={"a/other-7b": 32768}, ceiling=128_000
    )

    with pytest.raises(ContextWindowUnworkableError, match="130000") as raised:
        hold_model(
            connect(LMStudioConfig(host=HOST)),
            ModelRequest(identifier="a/other-7b", context_window=130_000),
            context_floor=FLOOR,
        )

    assert "128000" in str(raised.value)
    assert asked["order"] == []
