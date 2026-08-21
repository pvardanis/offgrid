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

# Which commands read the machine, and which name the profile. Listed rather
# than found, so a command added without a line here fails a test instead of
# quietly reaching the developer's own machine.
MEASURING = ("setup", "recommend")
READING_THE_PROFILE = ("setup", "doctor", "recommend", "run")


def answer_as_a_mac(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Answer with a fixed machine, and write nowhere real.

    :param monkeypatch: The test's patcher.
    :param tmp_path: Where the profile goes, and the agent's directory beside
        it.
    """
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

    # Its own patch because the path is settled as the module is imported, so
    # moving the home afterwards does not move what was already derived from
    # it — and what is kept about a runtime would land in the real one.
    monkeypatch.setattr(
        "offgrid.domain.running.discarded_windows.DEFAULT_PATH",
        tmp_path / "discarded-windows.json",
    )
