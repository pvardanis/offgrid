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

from offgrid.domain.running.answering import (
    find_resident_model,
    get_resident_model,
    hold_model,
)
from offgrid.domain.running.discarded_windows import DiscardedWindow
from offgrid.domain.running.discarding import refuse_to_ask_again
from offgrid.domain.running.model import ModelRequest
from offgrid.runtimes.lmstudio import connect
from offgrid.runtimes.lmstudio.config import LMStudioConfig
from offgrid.shared.exceptions import ModelUnavailableError
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


def test_a_runtime_holding_nothing_answers_a_caller_that_only_looks(monkeypatch):
    # `doctor` reports what it finds rather than acting on it, and holding
    # nothing is one of the things there is to find.
    answer_as_lm_studio(monkeypatch, cold={"a/cold-7b": 8192})

    assert find_resident_model(connect(LMStudioConfig(host=HOST))) is None


def test_a_runtime_holding_several_answers_with_the_first_of_them(monkeypatch):
    # The port promises a stable order and offgrid names the first of it. A
    # runtime naming a different one between two calls with nothing changed
    # is a report that moves under whoever is reading it.
    answer_as_lm_studio(monkeypatch, holding={RESIDENT: 8192, "a/also-held-7b": 8192})

    resident = find_resident_model(connect(LMStudioConfig(host=HOST)))

    assert resident is not None
    assert resident.identifier == RESIDENT


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
        connect(LMStudioConfig(host=HOST)),
        ModelRequest(),
        context_floor=FLOOR,
        was_refused=lambda identifier, window: False,
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
        was_refused=lambda identifier, window: False,
    )

    assert model.identifier == RESIDENT
    assert model.context_window == 16000
    assert asked["window"] == 16000


def test_naming_neither_a_model_nor_a_window_costs_no_load(monkeypatch):
    asked = answer_as_lm_studio(monkeypatch, holding={RESIDENT: 8192})

    model = hold_model(
        connect(LMStudioConfig(host=HOST)),
        ModelRequest(),
        context_floor=FLOOR,
        was_refused=lambda identifier, window: False,
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
        was_refused=lambda identifier, window: False,
    )

    assert model.identifier == "a/other-7b"
    assert model.context_window == 32768
    assert asked["let_go"] == [RESIDENT]


def _refused(**kept):
    """A predicate over records written by hand, one window per model.

    :param kept: The window each model was refused, by model.

    :return: Whether a model was refused exactly this window before.
    """
    return refuse_to_ask_again(
        {
            identifier: DiscardedWindow(
                host=HOST,
                identifier=identifier,
                asked_for=window,
                served=262_144,
                noticed_at="2026-08-21T14:31:07",
            )
            for identifier, window in kept.items()
        }
    )


def test_a_window_the_runtime_refused_before_is_not_asked_for_again(monkeypatch):
    # Asking again costs a release and a load that change nothing, and the
    # load is what throws the runtime's cached prefix away.
    asked = answer_as_lm_studio(monkeypatch, holding={RESIDENT: 262_144})

    model = hold_model(
        connect(LMStudioConfig(host=HOST)),
        ModelRequest(identifier=RESIDENT, context_window=131_072),
        context_floor=FLOOR,
        was_refused=_refused(**{RESIDENT: 131_072}),
    )

    assert model.context_window == 262_144
    assert asked["order"] == []


def test_a_window_the_runtime_was_never_asked_for_is_still_asked_for(monkeypatch):
    # A refusal is about the window it was given, not about the model. Reading
    # it as "this model gets no window" would throw away a number somebody
    # typed on the strength of an answer about a different one.
    asked = answer_as_lm_studio(monkeypatch, holding={RESIDENT: 262_144})

    hold_model(
        connect(LMStudioConfig(host=HOST)),
        ModelRequest(identifier=RESIDENT, context_window=30_000),
        context_floor=FLOOR,
        was_refused=_refused(**{RESIDENT: 200_000}),
    )

    assert asked["window"] == 30_000
