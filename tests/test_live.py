"""What a run does against the runtime on this machine.

Opt-in, with `uv run pytest -m live`. Everything else in the suite answers
with a double, which cannot tell the truth about a server that takes a name
it does not have, or that ids the second copy of a model the way a double was
told it does. This is the check that no double can stand in for.

It lets go of whatever the runtime is holding, which is what a run does.

Which agent starts is whatever the profile names, because nothing here is
about the agent. `test_live_pairs.py` is what covers both of them.
"""

import subprocess

import httpx
import pytest

from offgrid.runtimes.lmstudio import connect
from offgrid.runtimes.lmstudio.catalogue import (
    get_catalogue_payload,
    get_held_instances,
    get_loaded_models,
    parse_models_from_payload,
)
from offgrid.runtimes.lmstudio.config import LMStudioConfig
from offgrid.runtimes.lmstudio.holding import LOAD, LOAD_TIMEOUT_SECONDS
from tests.live_pairs import get_one_shot_args
from tests.live_runs import REFUSALS, STATED_WINDOW, run_offgrid
from tests.live_runtime import free_every_copy

pytestmark = pytest.mark.live


def test_every_copy_of_a_model_held_twice_is_let_go_of(host: str, held_twice: str):
    # A double can be told that the catalogue ids the second copy `:2` and
    # that the release takes that id. Only the server can say that it does,
    # and the whole reason to let go over HTTP is that it does.
    assert len(get_held_instances(get_catalogue_payload(host), held_twice)) == 2

    came_back = connect(LMStudioConfig(host=host)).let_go(held_twice)

    assert came_back is True
    assert get_held_instances(get_catalogue_payload(host), held_twice) == []


def test_a_run_says_which_model_answers_and_at_what_window(
    host: str, known: str, stored_agent: str
):
    # The window is what the runtime serves, which is only knowable after the
    # load: a catalogue read before it states the ceiling. Asked for none, it
    # is whatever the runtime's own configuration last remembered.
    finished = _run(known, stored_agent)

    assert known in finished.stderr
    assert "window" in finished.stderr


def test_a_model_the_runtime_does_not_have_is_refused_before_any_wait(
    host: str, stored_agent: str
):
    finished = _run("totally/made-up-model-9000", stored_agent)

    assert finished.returncode == 1
    assert "does not have" in finished.stderr
    assert [
        model.identifier for model in get_loaded_models(get_catalogue_payload(host))
    ] == []


def test_a_run_holds_the_model_at_the_window_it_was_asked_for(
    host: str, known: str, stored_agent: str
):
    # The number reaches the server and the server serves it. A double can be
    # told that the load endpoint takes `context_length` and that the
    # catalogue reports it back; only the server can say that it does.
    finished = _run(known, stored_agent, window=STATED_WINDOW)

    assert finished.returncode not in REFUSALS, finished.stderr
    assert f"window {STATED_WINDOW}" in finished.stderr, finished.stderr


def test_a_window_asked_for_leaves_one_copy_and_then_none(
    host: str, known: str, stored_agent: str
):
    # Changing a window means loading again, and a second load against this
    # server serves a second copy rather than replacing the first. What the
    # run owes is one copy while it runs and none after it.
    free_every_copy(host, known)
    httpx.post(
        f"http://{host}{LOAD}",
        json={"model": known, "context_length": 4096},
        timeout=LOAD_TIMEOUT_SECONDS,
    ).raise_for_status()

    finished = _run(known, stored_agent, window=STATED_WINDOW)

    assert finished.returncode not in REFUSALS, finished.stderr
    assert f"window {STATED_WINDOW}" in finished.stderr, finished.stderr
    assert get_held_instances(get_catalogue_payload(host), known) == [], finished.stderr


def test_a_window_above_the_ceiling_is_refused_rather_than_served(
    host: str, known: str, stored_agent: str
):
    # This server takes a window above a model's own maximum, answers that it
    # loaded it, and reports the impossible number back — so a double cannot
    # say that the refusal is offgrid's to make. Only this can.
    free_every_copy(host, known)
    ceiling = next(
        model.context_ceiling
        for model in parse_models_from_payload(get_catalogue_payload(host))
        if model.identifier == known
    )

    if ceiling is None:
        pytest.skip(f"{known} states no ceiling, so there is none to ask past")

    finished = _run(known, stored_agent, window=ceiling + 1)

    assert finished.returncode in REFUSALS, finished.stderr
    assert f"ceiling of {ceiling}" in finished.stderr, finished.stderr
    assert get_held_instances(get_catalogue_payload(host), known) == []


def _run(
    identifier: str, agent: str, window: int | None = None
) -> subprocess.CompletedProcess:
    """Start the agent the profile names against a model, and wait for it.

    :param identifier: The model to run against.
    :param agent: The agent the profile names, whose one-shot spelling this
        asks a question in.
    :param window: The window to ask for, or ``None`` to inherit.

    :return: What offgrid exited with, and what it said.
    """
    return run_offgrid(identifier, get_one_shot_args(agent), window)
