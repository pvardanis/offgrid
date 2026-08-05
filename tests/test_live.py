"""What a run does against the runtime and the agent on this machine.

Opt-in, with `uv run pytest -m live`. Everything else in the suite answers
with a double, which cannot tell the truth about a server that takes a name
it does not have, or a tool that reports success having freed nothing. This
is the check that no double can stand in for.

It lets go of whatever the runtime is holding, which is what a run does.
"""

import subprocess

import pytest

from offgrid.exceptions import OffgridError
from offgrid.profile import load as load_profile
from offgrid.runtimes.lmstudio import catalogue, loaded, parse_models

pytestmark = pytest.mark.live

ANSWER_SECONDS = 600


@pytest.fixture
def host() -> str:
    """Where the runtime listens, as the stored profile says.

    :return: The address from the profile.
    """
    try:
        return load_profile().host
    except OffgridError as error:
        pytest.skip(f"no profile to read the runtime's address from: {error}")


@pytest.fixture
def known(host: str, smoke_model: str) -> str:
    """Skip unless the runtime has the model the check needs.

    :param host: Where the runtime listens.
    :param smoke_model: The model the check loads.

    :return: The model identifier.
    """
    try:
        payload = catalogue(host)
    except OffgridError as error:
        pytest.skip(f"no runtime answering: {error}")

    if smoke_model not in {model.identifier for model in parse_models(payload)}:
        pytest.skip(f"{smoke_model} is not downloaded: `lms get {smoke_model}`")

    return smoke_model


def test_a_run_lets_go_of_the_model_it_held(host: str, known: str):
    finished = _run(known)

    assert finished.returncode == 0, finished.stderr
    assert [model.identifier for model in loaded(catalogue(host))] == []


def test_a_run_says_which_model_answers_and_at_what_context(host: str, known: str):
    # The context is the window the runtime serves, which is only knowable
    # after the load: a catalogue read before it states the ceiling.
    finished = _run(known)

    assert known in finished.stderr
    assert "context" in finished.stderr


def test_a_model_the_runtime_does_not_have_is_refused_before_any_wait(host: str):
    finished = _run("totally/made-up-model-9000")

    assert finished.returncode == 1
    assert "does not have" in finished.stdout
    assert [model.identifier for model in loaded(catalogue(host))] == []


def _run(identifier: str) -> subprocess.CompletedProcess:
    """Start an agent against a model and wait for it to finish.

    :param identifier: The model to run against.

    :return: What offgrid exited with, and what it said.
    """
    return subprocess.run(
        [
            "uv",
            "run",
            "offgrid",
            "run",
            "-m",
            identifier,
            "--",
            "-p",
            "reply with the two letters OK and nothing else",
        ],
        capture_output=True,
        text=True,
        timeout=ANSWER_SECONDS,
        check=False,
    )
