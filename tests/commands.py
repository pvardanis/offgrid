"""The command line, pointed away from this machine and this home.

One module per command, and each holds its own name for what it imported, so
a command is answered for once per command rather than once per name. Apart
from `tests/doubles.py` because what is stood in for here is offgrid's own
command line rather than anything a run talks to.
"""

from pathlib import Path

import pytest

from offgrid.domain.sizing.machine import Machine

GIB = 1024**3
MACHINE = Machine(
    chip="Apple M1 Max", memory_bytes=64 * GIB, wired_limit_bytes=56 * GIB
)

BIN = "bin"
"""The one directory on the `PATH` a command under test is given."""

# Which commands read the machine, and which name the profile. Listed rather
# than found, so a command added without a line here fails a test instead of
# quietly reaching the developer's own machine.
MEASURING = ("setup", "recommend")
READING_THE_PROFILE = ("setup", "doctor", "recommend", "run")


def install_agent(tmp_path: Path, command: str) -> Path:
    """Put a command on the `PATH` the tests own, as an install would.

    A file that is there and runnable, because that is all a `PATH` lookup
    asks; what it would do if run is the agent's business and no test's.

    :param tmp_path: The same directory `answer_as_a_mac` was given.
    :param command: What the agent is started by.

    :return: Where it was put, which is what a lookup should answer with.
    """
    installed = tmp_path / BIN / command
    installed.write_text("#!/bin/sh\n")
    installed.chmod(0o755)

    return installed


def answer_as_a_mac(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Answer with a fixed machine, and write nowhere real.

    The `PATH` is the test's own and starts empty, so what a command reports
    about an agent being installed is what the test arranged rather than what
    the machine running the suite happens to have.

    :param monkeypatch: The test's patcher.
    :param tmp_path: Where the profile goes, and the agent's directory beside
        it.
    """
    (tmp_path / BIN).mkdir(exist_ok=True)
    monkeypatch.setenv("PATH", str(tmp_path / BIN))

    for command in MEASURING:
        monkeypatch.setattr(f"offgrid.cli.{command}.detect", lambda: MACHINE)

    # The agent's config beside the commands, because it derives its own
    # directory rather than being handed one. A test that patched the commands
    # alone would reach the real home through it.
    for command in READING_THE_PROFILE:
        monkeypatch.setattr(
            f"offgrid.cli.{command}.DEFAULT_PATH", tmp_path / "profile.yaml"
        )

    monkeypatch.setattr("offgrid.domain.running.agent.OFFGRID_HOME", tmp_path)
