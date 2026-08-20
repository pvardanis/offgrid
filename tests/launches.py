"""What the agent would have been started with, without starting it.

Every test that reaches the end of a run needs this: the launch is the last
thing offgrid does, and the process it describes is the one thing the suite
must not actually run.
"""

import pytest


def record_launch(
    monkeypatch: pytest.MonkeyPatch, code: int = 0, order: list | None = None
) -> dict:
    """Record what would have been started, without starting it.

    :param monkeypatch: The test's patcher.
    :param code: What the agent exits with.
    :param order: A record of what the runtime was asked, to place the launch
        among it.

    :return: The environment and command the agent would have had.
    """
    seen: dict = {}

    def start(launch) -> int:
        if order is not None:
            order.append(("started", launch.argv[0]))
        seen.update(env=launch.env, argv=launch.argv)

        return code

    monkeypatch.setattr("offgrid.cli.run.start", start)

    return seen
