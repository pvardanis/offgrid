"""A launch, and the waiting that follows it.

An environment and an argument list. An agent adapter decides what goes in
one; this runs it, and stays alive until it is done.
"""

import os
import signal
import subprocess
from dataclasses import dataclass

# Being stopped by either of these means offgrid is going away, and the agent
# has to go with it rather than outlive the model it is talking to.
STOPS = (signal.SIGTERM, signal.SIGHUP)


@dataclass(frozen=True)
class Launch:
    """Everything needed to start an agent.

    :param env: Environment variables to add to the caller's own.
    :param argv: The command and its arguments.
    """

    env: dict[str, str]
    argv: list[str]


def start(launch: Launch) -> int:
    """Run the agent and wait for it.

    offgrid stays alive as its parent rather than handing over the process,
    because a model held in memory has to be let go by somebody once the
    agent is done with it. Being asked to stop is passed on for the same
    reason: an agent left running would be talking to a model offgrid is
    about to let go of.

    :param launch: The environment and command to run.

    :return: The agent's exit code, or what a shell reports for the signal
        that killed it.

    :raise OSError: When the agent cannot be started at all.
    """
    agent = subprocess.Popen(launch.argv, env={**os.environ, **launch.env})

    def pass_on(number: int, frame: object) -> None:
        """Stop the agent, so offgrid outlives it and can let the model go."""
        agent.terminate()

    replaced = [(number, signal.signal(number, pass_on)) for number in STOPS]

    try:
        code = agent.wait()
    finally:
        for number, handler in replaced:
            signal.signal(number, handler)

    return code if code >= 0 else 128 - code
