"""A launch, and the waiting that follows it.

An environment and an argument list. An agent adapter decides what goes in
one; this runs it, and stays alive until it is done.
"""

import errno
import os
import signal
import subprocess
from dataclasses import dataclass

# Being stopped by either of these means offgrid is going away, and the agent
# has to go with it rather than outlive the model it is talking to.
STOPS = (signal.SIGTERM, signal.SIGHUP)


@dataclass(frozen=True)
class Launch:
    """Everything needed to start an agent, and what to say before starting.

    :param env: Environment variables to add to the caller's own.
    :param argv: The command and its arguments.
    :param dropped: Variables the agent is started without, whatever the
        caller's own environment says. Asking for nothing is a claim about
        what the agent reads, and an agent inherits what offgrid does not
        name.
    :param caution: What a person is owed before this runs, where the agent
        will do something they would otherwise meet mid-session. Nothing for
        an agent with nothing to say, which is most launches.
    """

    env: dict[str, str]
    argv: list[str]
    dropped: frozenset[str] = frozenset()
    caution: str | None = None


def start(launch: Launch) -> int:
    """Run the agent and wait for it.

    offgrid stays alive as its parent rather than handing over the process,
    because a model held in memory has to be let go by somebody once the
    agent is done with it. Being asked to stop is passed on for the same
    reason: an agent left running would be talking to a model offgrid is
    about to let go of.

    The agent inherits this process's environment, so what a launch drops is
    taken back out after the two are merged: a setting offgrid deliberately
    did not make is one an exported variable would otherwise make for it.

    :param launch: The environment and command to run.

    :return: The agent's exit code, or what a shell reports for the signal
        that killed it.

    :raise OSError: When the agent cannot be started at all.
    """
    inherited: dict[str, str] = {**os.environ, **launch.env}

    for name in launch.dropped:
        inherited.pop(name, None)

    agent = subprocess.Popen(launch.argv, env=inherited)

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


def explain_why_it_would_not_start(command: str, error: OSError) -> str:
    """Say what stopped the agent starting, and what to do about that.

    A missing command and a command without the bit that makes it runnable
    fail the same way and are fixed differently, so the advice follows the
    reason rather than the operation.

    :param command: What was being started.
    :param error: Why it was not.

    :return: What to say.
    """
    advice = {
        errno.ENOENT: "Install it, or put it on PATH.",
        errno.EACCES: "It is there but not executable.",
    }.get(error.errno, "")

    return f"Could not start {command}: {error}. {advice}".rstrip()
