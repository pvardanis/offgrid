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

The adapter a conformance suite is asking about is here too, because three
files ask it and pytest reaches a fixture here without any of them importing
it.
"""

import subprocess
from pathlib import Path

import httpx
import pytest

from tests.commands import answer_as_a_mac
from tests.lmstudio_server import RESIDENT, SERVED, answer_as_lm_studio
from tests.runtimes_under_test import RUNTIMES_UNDER_TEST, RuntimeUnderTest

_run = subprocess.run

SMOKE_MODEL = "lfm2.5-1.2b-instruct-mlx"


@pytest.fixture(params=RUNTIMES_UNDER_TEST, ids=lambda under_test: under_test.name)
def runtime(request: pytest.FixtureRequest) -> RuntimeUnderTest:
    """The adapter this run of a conformance suite is asking about.

    :param request: The running test.

    :return: One adapter, and what standing its runtime in takes.
    """
    return request.param


@pytest.fixture
def here(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A fixed Mac writing nowhere real, and a runtime holding one model.

    What every test that drives a command against a stored profile starts
    from. A test wanting the runtime to answer differently says so itself:
    `answer_as_lm_studio` again replaces what this set up.

    :param monkeypatch: The test's patcher.
    :param tmp_path: Where the profile is written instead of a real home.

    :return: Where the profile is.
    """
    answer_as_lm_studio(monkeypatch, holding={RESIDENT: SERVED})
    answer_as_a_mac(monkeypatch, tmp_path)

    return tmp_path


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


@pytest.fixture(autouse=True)
def _no_real_home(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Keep what a run records out of the developer's own home.

    `hold_model` reads what a runtime discarded, so every test that holds a
    model touches this path whether or not it is about one. The default is
    settled as the module is imported, so a test moving `OFFGRID_HOME`
    afterwards does not move it.
    """
    if request.node.get_closest_marker("live"):
        return

    monkeypatch.setattr(
        "offgrid.domain.running.discarded_windows.DEFAULT_PATH",
        tmp_path / "discarded-windows.json",
    )
