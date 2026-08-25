"""The runtime a live check talks to, and the model it is asked to hold.

The arrangements rather than the checks. Two files ask for them — what a run
does against the runtime, and what it does for each pair — so they are here
rather than in either, and the root `conftest.py` registers this as a plugin
so both find them without importing a test module.

Everything here touches the machine it runs on, which is what `live` means.
"""

from collections.abc import Iterator

import httpx
import pytest

from offgrid.cli.binding import read_profile
from offgrid.domain.profile import DEFAULT_PATH
from offgrid.runtimes.lmstudio.catalogue import (
    get_catalogue_payload,
    get_held_instances,
    parse_models_from_payload,
)
from offgrid.runtimes.lmstudio.holding import LOAD, LOAD_TIMEOUT_SECONDS, unload_model
from offgrid.shared.exceptions import OffgridError


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
        free_every_copy(host, known)

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
        free_every_copy(host, known)


def free_every_copy(host: str, identifier: str) -> None:
    """Let go of every copy of a model, whatever any one of them answers.

    A release that raises partway leaves the copies after it resident, which
    is the outcome this exists to prevent — on the one kind of check allowed
    to touch the machine it runs on.

    :param host: Where the runtime listens.
    :param identifier: The model to free every copy of.
    """
    for instance in get_held_instances(get_catalogue_payload(host), identifier):
        try:
            unload_model(host, instance)
        except OffgridError as error:
            print(f"{instance} would not go: {error}")
