"""Holding one model, asked of every runtime adapter there is.

What `ensure_only` promises: the model as it is served rather than as
it is catalogued, held at the window it was asked for, alone in memory
afterwards — and which error arrives when it cannot be.

An adapter is done when this and its two companions pass.
`tests/runtimes_under_test.py` is where a second one joins, and it is the
only edit to the suite that adding one takes.
"""

import pytest

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

    model = runtime.connect().ensure_only("a/wanted-7b")

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

    connection.ensure_only("a/wanted-7b")

    assert [model.identifier for model in connection.read_held()] == ["a/wanted-7b"]


def test_a_model_already_held_is_answered_for_and_stays_held(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    # Letting go of the wanted model to load it again is the whole wait for no
    # change, and it throws away the prefix already in memory.
    runtime.arrange_serving(monkeypatch, holding={"a/wanted-7b": 8192})
    connection = runtime.connect()

    model = connection.ensure_only("a/wanted-7b")

    assert model.identifier == "a/wanted-7b"
    assert [held.identifier for held in connection.read_held()] == ["a/wanted-7b"]


def test_a_model_the_runtime_does_not_have_is_refused_by_name(
    runtime: RuntimeUnderTest, monkeypatch: pytest.MonkeyPatch
):
    runtime.arrange_serving(monkeypatch, holding={"a/held-7b": 8192})

    with pytest.raises(ModelUnavailableError) as refused:
        runtime.connect().ensure_only("a/absent-7b")

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
        runtime.connect().ensure_only("a/wanted-7b")

    assert "a/wanted-7b" in str(reported.value)
