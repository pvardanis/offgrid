"""Whether a Claude Code run would put the session on Anthropic's servers.

Its own module because it is read somewhere else entirely from the hosted-tool
reading beside it: there is no setting for this and nothing offgrid writes
turns it on or off, so the whole of the answer is the command line.
"""

from offgrid.domain.running.agent import Passthrough
from offgrid.domain.running.leaving import Reading, Status, Subject

# What `--help` on the version below says creates a session that runs
# somewhere other than this machine: `--cloud` opens one, and `--environment`
# opens one on a named self-hosted pool — off this machine either way, though
# only the first is Anthropic's own, which is why neither the message nor this
# comment says "Anthropic's servers" of both.
#
# The list is what was measured rather than everything `--help` hints at —
# `--teleport`, `--remote-control` and `--from-pr` each touch a session
# somewhere else and none was measured, which is issue #167. So the answer
# below names the two it looked at rather than claiming a complete list.
CLOUD_ARGUMENTS = ("--cloud", "--environment")

MEASURED_AGAINST = "claude 2.1.245"


def read_transcript_sharing(passthrough: Passthrough) -> Reading:
    """Say whether this run would send the session to Anthropic's servers.

    :param passthrough: What was handed to the agent unchanged.

    :return: What it found, and what to change.
    """
    asked = next((a for a in passthrough if _asks_for_a_cloud_session(a)), None)

    if asked is None:
        return Reading(
            subject=Subject.TRANSCRIPT_SHARING,
            status=Status.DENIED,
            detail=(
                f"Measured against {MEASURED_AGAINST}: neither "
                f"{' nor '.join(f'`{flag}`' for flag in CLOUD_ARGUMENTS)}, which "
                "`--help` calls cloud sessions, is here."
            ),
        )

    return Reading(
        subject=Subject.TRANSCRIPT_SHARING,
        status=Status.PERMITTED,
        detail=(
            f"`{asked}` runs this session in the cloud rather than here, so the "
            "whole of it leaves this machine whatever model the profile names."
        ),
        remedy="Drop the argument to run against the model held here.",
    )


def _asks_for_a_cloud_session(argument: str) -> bool:
    """Say whether one argument opens a session somewhere other than here.

    Matched at the start of an argument rather than anywhere inside one, so a
    prompt that quotes the flag does not count as typing it — the same rule
    `launching.py` reads `--setting-sources` by. Both spellings the agent takes
    are read, the flag alone and the flag carrying its value.

    :param argument: One argument, as it was typed.

    :return: True where it names one of the arguments measured.
    """
    return any(
        argument == flag or argument.startswith(f"{flag}=") for flag in CLOUD_ARGUMENTS
    )
