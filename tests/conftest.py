"""Keep the suite off the machine it is running on, and off the network.

Everything offgrid asks the runtime goes over HTTP, so refusing the transport
that talks to a socket is what keeps a test off the developer's model, and it
leaves the transport a test hands to httpx alone. `recommend` fetches a table
from a third party, and the same refusal keeps the suite from depending on
someone else's site being up to pass.

The runtime's own tool is refused beside it. Nothing calls it, and that is the
point: a release that went back to shelling out would evict the developer's
model invisibly, because the caller reports the failure rather than raising.

A test marked `live` reaches both on purpose, and is the one thing let
through.
"""

import subprocess

import httpx
import pytest

_run = subprocess.run

SMOKE_MODEL = "lfm2.5-1.2b-instruct-mlx"


def pytest_addoption(parser: pytest.Parser) -> None:
    """Let another machine name a different model for the live checks.

    :param parser: The command line parser pytest is building.
    """
    parser.addoption(
        "--smoke-model",
        default=SMOKE_MODEL,
        help=(
            "Model the live checks load. Small is the point: it proves the "
            "plumbing, not what the model says."
        ),
    )


@pytest.fixture
def smoke_model(request: pytest.FixtureRequest) -> str:
    """The model the live checks load.

    :param request: The running test.

    :return: The model identifier, as the runtime's catalogue states it.
    """
    return str(request.config.getoption("--smoke-model"))


@pytest.fixture(autouse=True)
def _no_real_runtime(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refuse to run the runtime's tool, which nothing is meant to reach for."""
    if request.node.get_closest_marker("live"):
        return

    def refuse(argv, *args, **kwargs):
        if isinstance(argv, list | tuple) and argv and "lms" in str(argv[0]):
            raise AssertionError(
                f"A test reached the real runtime: {list(argv)}. offgrid asks "
                "LM Studio over HTTP; serve it with tests.doubles instead."
            )

        return _run(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", refuse)


@pytest.fixture(autouse=True)
def _no_network(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refuse the transport that reaches a socket, whatever asked for it."""
    if request.node.get_closest_marker("live"):
        return

    def refuse(self: httpx.HTTPTransport, sent: httpx.Request) -> httpx.Response:
        raise AssertionError(
            f"A test reached the network: {sent.method} {sent.url}. "
            "Patch the fetch, or serve it with tests.doubles.serve_get."
        )

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)
