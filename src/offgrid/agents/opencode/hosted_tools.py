"""Whether OpenCode offers a tool offgrid cannot run on this machine.

Answered from a measurement rather than from a configuration, because it is a
fact about a version: there is nothing in a file that could change it, and an
adapter with nothing to check still owes the claim and the evidence for it.
"""

from offgrid.domain.running.leaving import Reading, Status, Subject

# The tool list, measured on 2026-08-24 the way `docs/decisions.md` measured
# 1.18.14, by reading the tools it sends — bash, edit, glob, grep, read, skill,
# task, todowrite, webfetch and write, every one of them running on this
# machine. Dated and versioned because it is a claim about a release, and the
# sharing reading beside it was measured on a later one: naming one version for
# both would claim a reading nobody took.
HOSTED_MEASURED_AGAINST = "opencode 1.18.20"


def read_hosted_tools() -> Reading:
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
