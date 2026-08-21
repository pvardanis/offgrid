"""Which windows a run is refused at, and which ones it is not.

A window is bounded at both ends, and both bounds are the numbers themselves:
a window exactly at the floor starts the agent and one exactly at the ceiling
is served, so each bound is checked at the number as well as past it.

The runtime is a real connection with the server stood in for, so a refusal
costs no load and no release — which is what `asked["order"] == []` says. The
ceiling is read from the catalogue first, so that one does cost a request.
"""

import pytest

from offgrid.domain.running.answering import hold_model
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
FLOOR = 25_000


def _hold(window: int | None, identifier: str | None = None):
    """Ask for a model at a window, against the agent's floor.

    :param window: The window to ask for.
    :param identifier: The model to ask for, or ``None`` for the resident one.

    :return: The model that would answer.
    """
    return hold_model(
        connect(LMStudioConfig(host=HOST)),
        ModelRequest(identifier=identifier, context_window=window),
        context_floor=FLOOR,
        was_refused=lambda identifier, window: False,
    )


def test_a_window_below_the_agents_floor_is_refused_before_any_load(monkeypatch):
    # The agent's prompt and tool definitions do not fit below its floor, so
    # it fails at startup — after a load costing tens of seconds nobody gets
    # back. Both numbers are named, so the next one to type is in the message
    # rather than in the source.
    asked = answer_as_lm_studio(monkeypatch, holding={RESIDENT: 8192})

    with pytest.raises(ContextWindowUnworkableError) as raised:
        _hold(8000)

    # The whole sentence, so that a message naming one number twice, or
    # naming neither operand, is a failure rather than a phrasing.
    assert "A window of 8000 is below the agent's floor of 25000" in str(raised.value)
    assert asked["order"] == []


def test_a_window_exactly_at_the_floor_is_one_the_agent_starts_in(monkeypatch):
    # The floor is the smallest window that works, not the first that does
    # not, and a run asking for exactly it is the one the message above told
    # somebody to make.
    asked = answer_as_lm_studio(monkeypatch, holding={RESIDENT: 8192})

    assert _hold(FLOOR).context_window == FLOOR
    assert asked["window"] == FLOOR


def test_a_window_above_the_models_ceiling_is_refused_before_any_load(monkeypatch):
    # The runtime takes this one without complaint and serves the impossible
    # number back, so nobody downstream can tell it is not real. offgrid
    # refuses it on the person's behalf, and names what the model does state.
    asked = answer_as_lm_studio(
        monkeypatch, cold={"a/other-7b": 32768}, ceiling=128_000
    )

    with pytest.raises(ContextWindowUnworkableError) as raised:
        _hold(130_000, identifier="a/other-7b")

    assert "A window of 130000 is above a/other-7b's ceiling of 128000" in str(
        raised.value
    )
    assert asked["order"] == []


def test_a_window_exactly_at_the_ceiling_is_one_the_model_serves(monkeypatch):
    # The ceiling is the most a model can be served at, and asking for all of
    # it is what the refusal above says to do.
    asked = answer_as_lm_studio(
        monkeypatch, cold={"a/other-7b": 32768}, ceiling=128_000
    )

    assert _hold(128_000, identifier="a/other-7b").context_window == 128_000
    assert asked["window"] == 128_000


def test_a_model_stating_no_ceiling_leaves_nothing_to_measure_against(monkeypatch):
    # A runtime that describes a model sparsely says nothing about what it
    # could serve. Reading that as a ceiling of nothing would refuse every
    # window against a number nobody stated.
    asked = answer_as_lm_studio(monkeypatch, cold={"a/mystery": 32768}, ceiling=None)

    assert _hold(300_000, identifier="a/mystery").context_window == 300_000
    assert asked["window"] == 300_000


def test_a_model_the_runtime_does_not_have_is_still_refused_by_name(monkeypatch):
    # The ceiling check finds no such model and says nothing about it, so the
    # runtime's own answer is the one that arrives: by name, with the address
    # and what to run to see what there is.
    answer_as_lm_studio(monkeypatch, holding={RESIDENT: 8192})

    with pytest.raises(ModelUnavailableError, match="a/absent-7b"):
        _hold(32768, identifier="a/absent-7b")


def test_the_ceiling_measured_against_is_the_one_the_model_asked_for_states(
    monkeypatch,
):
    # A catalogue holds many models and only one of them is being held. Read
    # the ceiling off whichever entry comes first and a small model is served
    # a window a large one could have honoured.
    asked = answer_as_lm_studio(
        monkeypatch,
        cold={"a/roomy-70b": 32768, "a/small-1b": 4096},
        ceilings={"a/roomy-70b": 262_144, "a/small-1b": 40960},
    )

    with pytest.raises(ContextWindowUnworkableError) as raised:
        _hold(200_000, identifier="a/small-1b")

    assert "above a/small-1b's ceiling of 40960" in str(raised.value)
    assert asked["order"] == []
