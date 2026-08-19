"""Holding one model, asked of every runtime adapter there is.

What `ensure_only` promises: the model as it is served rather than as
it is catalogued, held at the window it was asked for, alone in memory
afterwards — and which error arrives when it cannot be.

An adapter is done when this and its two companions pass.
`tests/runtimes_under_test.py` is where a second one joins, and it is the
only edit to the suite that adding one takes.
"""

import pytest

from offgrid.domain.running.model import ModelRequest
from offgrid.shared.exceptions import (
    ModelNotHeldError,
    ModelUnavailableError,
)
from tests.runtimes_under_test import RuntimeUnderTest


def test_a_model_is_answered_for_as_it_is_served_not_as_it_is_catalogued(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # A catalogue entry states a ceiling. A model in memory states the window
    # it is actually served at. Sizing an agent's context from the ceiling
    # means it never compacts and the runtime truncates the prefix instead,
    # which is the failure compacting exists to avoid.
    runtime.arrange_serving(monkeypatch, cold={"a/wanted-7b": 32768}, catalogued=262144)

    model = runtime.connect().ensure_only(ModelRequest(identifier="a/wanted-7b"))

    assert model.identifier == "a/wanted-7b"
    assert (model.context_window, model.context_ceiling) == (32768, 262144)


def test_only_the_model_that_will_answer_is_held_afterwards(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # One machine, one pool of memory. What reaching that state costs is the
    # adapter's business; that it was reached is not.
    runtime.arrange_serving(
        monkeypatch, holding={"a/held-7b": 8192}, cold={"a/wanted-7b": 8192}
    )
    connection = runtime.connect()

    connection.ensure_only(ModelRequest(identifier="a/wanted-7b"))

    assert [model.identifier for model in connection.read_held()] == ["a/wanted-7b"]


def test_a_model_already_held_is_answered_for_and_stays_held(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # Letting go of the wanted model to load it again is the whole wait for no
    # change, and it throws away the prefix already in memory.
    runtime.arrange_serving(monkeypatch, holding={"a/wanted-7b": 8192})
    connection = runtime.connect()

    model = connection.ensure_only(ModelRequest(identifier="a/wanted-7b"))

    assert model.identifier == "a/wanted-7b"
    assert [held.identifier for held in connection.read_held()] == ["a/wanted-7b"]


def test_a_model_is_held_at_the_window_asked_for(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # The window is what the agent is sized to, and a runtime left to serve
    # whatever it last remembered makes that number nobody's decision.
    runtime.arrange_serving(monkeypatch, cold={"a/wanted-7b": 32768})

    model = runtime.connect().ensure_only(
        ModelRequest(identifier="a/wanted-7b", context_window=8000)
    )

    assert model.context_window == 8000


def test_a_model_is_answered_for_at_the_window_served_not_the_one_asked_for(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # A runtime is free to honour a window with a different one. Echoing back
    # the number that was typed would size the agent to a window nothing is
    # serving, which is the failure reading the served window exists to
    # prevent — reintroduced on the path that asks for one.
    runtime.arrange_serving_regardless(
        monkeypatch, cold={"a/wanted-7b": 4096}, serves=32768
    )

    model = runtime.connect().ensure_only(
        ModelRequest(identifier="a/wanted-7b", context_window=200000)
    )

    assert model.context_window == 32768


def test_a_model_asked_for_with_no_window_is_served_as_the_runtime_chose(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # Saying nothing inherits. Any default would replace what a person set in
    # the runtime with a number offgrid made up.
    runtime.arrange_serving(monkeypatch, cold={"a/wanted-7b": 32768})

    model = runtime.connect().ensure_only(ModelRequest(identifier="a/wanted-7b"))

    assert model.context_window == 32768


def test_a_model_already_held_at_the_window_asked_for_is_left_alone(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # A reload buys nothing and costs the prefix already prefilled against
    # this model, which is the expensive half of a turn.
    runtime.arrange_serving(monkeypatch, holding={"a/wanted-7b": 8000})
    connection = runtime.connect()

    model = connection.ensure_only(
        ModelRequest(identifier="a/wanted-7b", context_window=8000)
    )

    assert model.context_window == 8000
    assert [held.identifier for held in connection.read_held()] == ["a/wanted-7b"]


def test_a_model_held_at_another_window_is_held_once_at_the_new_one(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # A model in memory cannot be told a new window, so it is let go of and
    # loaded again. Exactly one copy is held afterwards: a runtime serving the
    # same model twice over is memory gone for the rest of the session.
    runtime.arrange_serving(monkeypatch, holding={"a/wanted-7b": 8000})
    connection = runtime.connect()

    model = connection.ensure_only(
        ModelRequest(identifier="a/wanted-7b", context_window=16000)
    )

    assert model.context_window == 16000
    assert [held.identifier for held in connection.read_held()] == ["a/wanted-7b"]


def test_a_model_the_runtime_does_not_have_is_refused_by_name(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    runtime.arrange_serving(monkeypatch, holding={"a/held-7b": 8192})

    with pytest.raises(ModelUnavailableError) as refused:
        runtime.connect().ensure_only(ModelRequest(identifier="a/absent-7b"))

    said = str(refused.value)
    assert "a/absent-7b" in said
    assert runtime.address in said
    assert "offgrid doctor" in said


def test_a_model_the_runtime_took_and_does_not_hold_is_reported(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # A runtime that accepted the load and is holding nothing has answered
    # every question but the one that matters, so reading back what is held is
    # the only way to find out. Which error arrives says which of the two
    # happened, and a caller branches on that.
    runtime.arrange_taking_without_holding(monkeypatch, model="a/wanted-7b")

    with pytest.raises(ModelNotHeldError) as reported:
        runtime.connect().ensure_only(ModelRequest(identifier="a/wanted-7b"))

    assert "a/wanted-7b" in str(reported.value)
