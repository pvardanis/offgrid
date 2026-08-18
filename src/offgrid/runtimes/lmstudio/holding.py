"""Taking a model into memory, and letting one go.

The two calls that move weights. Both are requests to the server, so nothing
here needs a program on this machine's PATH.
"""

import httpx

from offgrid.shared.exceptions import RuntimeUnreachableError

MESSAGES = "/v1/messages"
UNLOAD = "/api/v1/models/unload"

# Weights come off disk at gigabytes a second, so a large model takes tens of
# seconds and a cold cache takes longer.
LOAD_TIMEOUT_SECONDS = 300

# Freeing memory is the runtime dropping what it already has, so this is a
# ceiling on a machine that is swapping rather than a wait anyone should see.
UNLOAD_TIMEOUT_SECONDS = 30


def load_model(
    host: str, identifier: str, timeout: float = LOAD_TIMEOUT_SECONDS
) -> None:
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
    except httpx.RequestError as error:
        raise RuntimeUnreachableError(
            _explain_why_the_load_did_not_arrive(
                error, host=host, identifier=identifier, timeout=timeout
            )
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


def unload_model(
    host: str, instance: str, timeout: float = UNLOAD_TIMEOUT_SECONDS
) -> None:
    """Ask the runtime to let go of one instance it is holding.

    The endpoint names an instance rather than a model, because LM Studio can
    hold the same model more than once and freeing memory is per copy.

    Whether the memory actually came back is the catalogue's answer rather
    than this one, so a caller that needs to know reads it back.

    :param host: Address the runtime listens on.
    :param instance: The instance to let go of, as the catalogue ids it.
    :param timeout: How long to wait before giving up.

    :raise RuntimeUnreachableError: When the runtime cannot be reached, or
        refuses the release. An instance it is not holding is a 404 saying so,
        which is how a release that freed nothing announces itself.
    """
    url = f"http://{host}{UNLOAD}"

    try:
        response = httpx.post(url, json={"instance_id": instance}, timeout=timeout)
    except httpx.RequestError as error:
        raise RuntimeUnreachableError(
            f"The release of {instance} did not reach http://{host}: {error}. "
            "Check what is listening there."
        ) from error

    if response.is_error:
        raise RuntimeUnreachableError(
            f"The runtime answered {response.status_code} letting go of "
            f"{instance}: {_read_the_complaint(response)}"
        )


def _read_the_complaint(response: httpx.Response) -> str:
    """Read the reason out of a refusal.

    LM Studio answers one with ``{"error": {"message": ...}}``. Anything else
    — a proxy's error page, a body carrying no reason — comes back as it
    arrived, which is more than nothing to go on.

    :param response: What the runtime answered with.

    :return: What it said about refusing.
    """
    try:
        body = response.json()
    except ValueError:
        body = None

    said = None
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        said = body["error"].get("message")

    return str(said or response.text.strip() or "no reason given")


def _explain_why_the_load_did_not_arrive(
    error: httpx.RequestError, *, host: str, identifier: str, timeout: float
) -> str:
    """Say which way the load failed, and what to do about that one.

    :param error: What httpx raised.
    :param host: Address the runtime was expected on.
    :param identifier: The model being loaded.
    :param timeout: How long it was given.

    :return: What to tell whoever ran offgrid.
    """
    # Most specific first: a `TimeoutException` is a `TransportError`, which is
    # a `RequestError`, so the first that matches is the one that fits.
    said = {
        httpx.TimeoutException: (
            f"{identifier} did not finish loading within {timeout:.0f}s. "
            "Load it in the runtime directly, or allow longer."
        ),
        httpx.TransportError: (
            f"No model server answered at http://{host}. "
            "Start LM Studio, or point offgrid elsewhere with --host."
        ),
        httpx.RequestError: (
            f"The answer to loading {identifier} could not be read: {error}. "
            f"Check what is listening at http://{host}."
        ),
    }

    return next(sentence for kind, sentence in said.items() if isinstance(error, kind))
