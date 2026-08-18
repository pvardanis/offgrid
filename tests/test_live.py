"""What a run does against the runtime and the agent on this machine.

Opt-in, with `uv run pytest -m live`. Everything else in the suite answers
with a double, which cannot tell the truth about a server that takes a name
it does not have, or that ids the second copy of a model the way a double was
told it does. This is the check that no double can stand in for.

It lets go of whatever the runtime is holding, which is what a run does.
"""

import subprocess
from collections.abc import Iterator

import httpx
import pytest

from offgrid.binding import read_profile
from offgrid.domain.profile import DEFAULT_PATH
from offgrid.runtimes.lmstudio import connect
from offgrid.runtimes.lmstudio.catalogue import (
    get_catalogue_payload,
    get_held_instances,
    get_loaded_models,
    parse_models_from_payload,
)
from offgrid.runtimes.lmstudio.config import LMStudioConfig
from offgrid.runtimes.lmstudio.holding import LOAD, LOAD_TIMEOUT_SECONDS, unload_model
from offgrid.shared.exceptions import OffgridError

pytestmark = pytest.mark.live

ANSWER_SECONDS = 600


@pytest.fixture
def host() -> str:
    """Where the runtime listens, as the stored profile says.

    :return: The address from the profile.
    """
    try:
        return read_profile(DEFAULT_PATH).runtime.host
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
        payload = get_catalogue_payload(host)
    except OffgridError as error:
        pytest.skip(f"no runtime answering: {error}")

    if smoke_model not in {
        model.identifier for model in parse_models_from_payload(payload)
    }:
        pytest.skip(f"{smoke_model} is not downloaded: `lms get {smoke_model}`")

    return smoke_model


@pytest.fixture
def held_twice(host: str, known: str) -> Iterator[str]:
    """Hold the model exactly twice, and free what is left of it afterwards.

    Whatever was held first is freed, so that two loads mean two copies. A
    developer with this model already open in LM Studio would otherwise get
    three, and a count that says nothing about what the release did.

    :param host: Where the runtime listens.
    :param known: The model the check loads.

    :yield: The model identifier, with two copies of it in memory.
    """
    try:
        _free(host, known)

        for _ in range(2):
            httpx.post(
                f"http://{host}{LOAD}",
                json={"model": known},
                timeout=LOAD_TIMEOUT_SECONDS,
            ).raise_for_status()

        yield known
    finally:
        # Including a load that failed after the first one landed, which would
        # otherwise leave this machine holding what the check is about.
        _free(host, known)


def _free(host: str, identifier: str) -> None:
    """Let go of every copy of a model, whatever any one of them answers.

    A release that raises partway leaves the copies after it resident, which
    is the outcome this exists to prevent — on the one check allowed to touch
    the machine it runs on.

    :param host: Where the runtime listens.
    :param identifier: The model to free every copy of.
    """
    for instance in get_held_instances(get_catalogue_payload(host), identifier):
        try:
            unload_model(host, instance)
        except OffgridError as error:
            print(f"{instance} would not go: {error}")


REFUSALS = (1, 127)


def test_every_copy_of_a_model_held_twice_is_let_go_of(host: str, held_twice: str):
    # A double can be told that the catalogue ids the second copy `:2` and
    # that the release takes that id. Only the server can say that it does,
    # and the whole reason to let go over HTTP is that it does.
    assert len(get_held_instances(get_catalogue_payload(host), held_twice)) == 2

    came_back = connect(LMStudioConfig(host=host)).let_go(held_twice)

    assert came_back is True
    assert get_held_instances(get_catalogue_payload(host), held_twice) == []


def test_a_run_lets_go_of_the_model_it_held(host: str, known: str):
    # Not that the agent succeeded: a model this small answers a 21k-token
    # prefix with whatever it can, and that is its business. What offgrid
    # owes is that it got that far, and that the memory came back.
    finished = _run(known)

    assert finished.returncode not in REFUSALS, finished.stderr
    # Exit codes alone cannot tell a run that held a model from one that
    # never reached the runtime — a usage error exits 2 and leaves nothing
    # loaded, which would satisfy the rest of this on its own.
    assert known in finished.stderr
    assert [
        model.identifier for model in get_loaded_models(get_catalogue_payload(host))
    ] == [], finished.stderr


def test_a_run_says_which_model_answers_and_at_what_context(host: str, known: str):
    # The context is the window the runtime serves, which is only knowable
    # after the load: a catalogue read before it states the ceiling.
    finished = _run(known)

    assert known in finished.stderr
    assert "context" in finished.stderr


def test_a_model_the_runtime_does_not_have_is_refused_before_any_wait(host: str):
    finished = _run("totally/made-up-model-9000")

    assert finished.returncode == 1
    assert "does not have" in finished.stderr
    assert [
        model.identifier for model in get_loaded_models(get_catalogue_payload(host))
    ] == []


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
