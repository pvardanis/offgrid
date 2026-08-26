"""What an OpenCode run could send off this machine, read out of what it loads.

Two subjects and two modules, the same shape the Claude Code adapter uses.
Nothing hosted is answered here from a measurement, since it is a fact about a
version rather than about a configuration; sharing is read out of the command
line and the file, in `sharing.py`.
"""

from pathlib import Path

from offgrid.agents.opencode.sharing import read_transcript_sharing
from offgrid.domain.running.agent import Passthrough
from offgrid.domain.running.leaving import Reading, Status, Subject

# The tool list, measured on 2026-08-24 the way `docs/decisions.md` measured
# 1.18.14, by reading the tools it sends — bash, edit, glob, grep, read, skill,
# task, todowrite, webfetch and write, every one of them running on this
# machine. Dated and versioned because it is a claim about a release, and the
# sharing reading beside it was measured on a later one: naming one version for
# both would claim a reading nobody took.
HOSTED_MEASURED_AGAINST = "opencode 1.18.20"


def read_what_leaves_this_machine(
    settings: Path, passthrough: Passthrough
) -> tuple[Reading, ...]:
    """Say what this OpenCode run could send off this machine.

    :param settings: The configuration file offgrid writes for this agent.
    :param passthrough: What was handed to the agent unchanged.

    :return: One reading for each way off this machine.

    :raise AgentSettingsError: When the file is there and cannot be read.
    """
    return (
        _read_hosted_tools(),
        read_transcript_sharing(settings, passthrough),
    )


def _read_hosted_tools() -> Reading:
    """Say that OpenCode offers no tool offgrid cannot run here.

    :return: That there is nothing to permit, and what that was measured
        against.
    """
    return Reading(
        subject=Subject.HOSTED_TOOLS,
        status=Status.NONE_OFFERED,
        detail=(
            f"Measured against {HOSTED_MEASURED_AGAINST}: every tool it offers "
            "runs on this machine, and it talks to whatever provider it is "
            "pointed at rather than to one vendor, so there is nothing hosted "
            "to deny."
        ),
    )
