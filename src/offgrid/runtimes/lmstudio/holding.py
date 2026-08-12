"""Taking a model into memory, and letting one go.

The two calls that move weights, and they move them differently: a load is a
request to the server, and a release is LM Studio's own tool, talking to the
copy running on this machine.
"""

import subprocess

import httpx

from offgrid.exceptions import RuntimeUnreachableError
from offgrid.runtimes.lmstudio.catalogue import (
    get_catalogue_payload,
    get_loaded_models,
    nothing_answered_at,
)

MESSAGES = "/v1/messages"

# Weights come off disk at gigabytes a second, so a large model takes tens of
# seconds and a cold cache takes longer.
LOAD_TIMEOUT_SECONDS = 300

# LM Studio has an HTTP unload and has since 0.4.0, but it takes an
# `instance_id` that the `/api/v0` catalogue this adapter reads does not carry.
# Its own tool takes a model name, and talks to the copy running on this
# machine.
TOOL = "lms"


def load(host: str, identifier: str, timeout: float = LOAD_TIMEOUT_SECONDS) -> None:
    """Hold a model in memory, waiting until it is ready to answer.

    Asking for a single token is what makes the runtime load it. Doing that
    here rather than leaving it to the first real request means the wait is
    visible and attributable, instead of a silence in the middle of a turn.

    :param host: Address the runtime listens on.
    :param identifier: The model to load.
    :param timeout: How long to wait before giving up.

    :raise RuntimeUnreachableError: When the load does not finish in time,
        when the runtime refuses it, or when another model answers. A name
        LM Studio does not have is answered 200 by whatever is loaded, and
        the model named in the reply is what gives that away.
    """
    url = f"http://{host}{MESSAGES}"
    body = {
        "model": identifier,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hi"}],
    }

    try:
        response = httpx.post(url, json=body, timeout=timeout)
    except httpx.TimeoutException as error:
        raise RuntimeUnreachableError(
            f"{identifier} did not finish loading within {timeout:.0f}s. "
            "Load it in the runtime directly, or allow longer."
        ) from error
    except httpx.TransportError as error:
        raise RuntimeUnreachableError(nothing_answered_at(host)) from error
    except httpx.RequestError as error:
        raise RuntimeUnreachableError(
            f"The answer to loading {identifier} could not be read: {error}. "
            f"Check what is listening at http://{host}."
        ) from error

    if response.is_error:
        raise RuntimeUnreachableError(
            f"The runtime answered {response.status_code} loading {identifier}. "
            "Check the name against `offgrid doctor`, and that it has room."
        )

    try:
        answer = response.json()
    except ValueError as error:
        raise RuntimeUnreachableError(
            f"{url} answered {response.status_code} loading {identifier} with "
            f"{response.headers.get('content-type', 'no type')}, not JSON. "
            f"Is http://{host} really LM Studio?"
        ) from error

    answered = answer.get("model") if isinstance(answer, dict) else None
    if answered and answered != identifier:
        raise RuntimeUnreachableError(
            f"{identifier} was asked for and {answered} answered. LM Studio "
            "takes a name it does not have and lets whatever is loaded reply, "
            "so check the name against `offgrid doctor`."
        )


def unload(host: str, identifier: str) -> None:
    """Let go of a model, and confirm the memory it held came back.

    The tool exits 0 for a name it does not know, printing ``Model Not
    Found`` and freeing nothing, so its exit code alone cannot say whether
    anything was let go. The catalogue is what settles it.

    :param host: Address the runtime listens on.
    :param identifier: The model to unload.

    :raise RuntimeUnreachableError: When the runtime's tool is missing, when
        it refuses, or when the model is still held afterwards. Memory that
        stays held is worth saying out loud, since the machine has one pool
        and everything else on it shares it.
    """
    try:
        finished = subprocess.run(
            [TOOL, "unload", identifier],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise RuntimeUnreachableError(
            f"Could not run {TOOL} to unload {identifier}: {error}. "
            "It ships with LM Studio; check it is on PATH."
        ) from error

    if finished.returncode != 0:
        complaint = (
            finished.stderr.strip() or finished.stdout.strip() or "no reason given"
        )
        raise RuntimeUnreachableError(
            f"{TOOL} would not unload {identifier}: {complaint}"
        )

    if any(
        model.identifier == identifier
        for model in get_loaded_models(get_catalogue_payload(host))
    ):
        raise RuntimeUnreachableError(
            f"{TOOL} exited cleanly, but http://{host} is still holding "
            f"{identifier}: {finished.stdout.strip() or 'it said nothing'}. "
            "Let it go in LM Studio directly."
        )
