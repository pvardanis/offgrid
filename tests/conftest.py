"""Keep the suite off the machine it is running on, and off the network.

Unloading a model reaches for LM Studio's own tool, which acts on whatever
server is running. A test that forgets to intercept it evicts the developer's
model, and does so invisibly, because the caller reports the failure rather
than raising. Refusing the call here means a test cannot reach the runtime by
omission.

`recommend` fetches a table from a third party, and a suite that reaches for
it depends on someone else's site being up to pass. Refusing the transport
that talks to a socket leaves the one a test hands to httpx alone.

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
    """Refuse to run the runtime's tool, whatever a test forgot to patch."""
    if request.node.get_closest_marker("live"):
        return

    def refuse(argv, *args, **kwargs):
        if isinstance(argv, list | tuple) and argv and "lms" in str(argv[0]):
            raise AssertionError(
                f"A test reached the real runtime: {list(argv)}. "
                "Patch offgrid.hold.unload, or the adapter's subprocess call."
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
