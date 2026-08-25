"""Starting a real `offgrid run`, and putting back what one leaves behind.

A live run is a subprocess, so nothing a test patches reaches it: it reads the
stored profile and writes into the real home. Both files that start one ask
for the same two things, so they are here, and the root `conftest.py`
registers this as a plugin so both find them.
"""

import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from offgrid.domain.running.discarded_windows import DEFAULT_PATH as KEPT_PATH

ANSWER_SECONDS = 600

PROMPT = "reply with the two letters OK and nothing else"

# A window to ask for and read back, rather than inheriting whatever the
# profile stores. Above both agents' floors so either starts, and small enough
# that the smoke model is served at it rather than clamped to something else.
STATED_WINDOW = 32768

# What a run exits with when it refused before the agent, and what offgrid
# exits with when the agent would not start. Neither is a run that reached
# the agent, which is what every check that starts one is about.
REFUSALS = (1, 127)


def run_offgrid(
    identifier: str, passthrough: list[str], window: int | None = None
) -> subprocess.CompletedProcess:
    """Start an agent against a model and wait for it to finish.

    :param identifier: The model to run against.
    :param passthrough: What the agent is asked, in its own spelling.
    :param window: The window to ask for, or ``None`` to inherit.

    :return: What offgrid exited with, and what it said.
    """
    asked = ["--context-window", str(window)] if window else []

    return subprocess.run(
        ["uv", "run", "offgrid", "run", "-m", identifier, *asked, "--", *passthrough],
        capture_output=True,
        text=True,
        timeout=ANSWER_SECONDS,
        check=False,
    )


@pytest.fixture(autouse=True)
def keep_what_a_live_run_records_out_of_the_way(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Iterator[None]:
    """Put back what a live run writes about a discarded window.

    Nothing about a discarded window expires, so a record left behind here
    would quietly stop a later run of this person's own asking for that
    window.

    :param request: The running test, which is left alone unless it is live.
    :param tmp_path: Where the real file is held while the test runs.

    :yield: Nothing; what was there is put back afterwards.
    """
    if request.node.get_closest_marker("live") is None:
        yield
        return

    kept = tmp_path / "discarded-windows.json"
    had_one = KEPT_PATH.exists()

    if had_one:
        shutil.copy2(KEPT_PATH, kept)

    try:
        yield
    finally:
        KEPT_PATH.unlink(missing_ok=True)

        if had_one:
            shutil.copy2(kept, KEPT_PATH)
