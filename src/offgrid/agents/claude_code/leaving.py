"""What a Claude Code run could send off this machine, read out of what it loads.

Two subjects and two places to read them. WebSearch is settled by a settings
file and by the argument deciding whether that file is loaded at all; publishing
the session is settled by the command line alone, since offgrid writes nothing
asking for it.
"""

from pathlib import Path

from offgrid.agents.claude_code.configuring import get_denied_tools
from offgrid.agents.claude_code.launching import (
    SOURCES,
    WRITTEN_SOURCE,
    get_dropped_settings_sources,
)
from offgrid.domain.running.agent import Passthrough
from offgrid.domain.running.config_editing import read_as_json, read_what_config_is_kept
from offgrid.domain.running.leaving import Reading, Status, Subject

SEARCH = "WebSearch"

# What `--help` on claude 2.1.245 says creates a session that runs on
# Anthropic's servers: `--cloud` opens one, and `--environment` opens one on a
# named self-hosted pool. Either sends the whole session off this machine
# whatever model the profile names, so a run carrying one is not a local run.
#
# Read off the command line rather than off a file, because there is no
# setting to read: nothing offgrid writes turns this on or off. The list is
# what was measured rather than everything `--help` hints at — `--teleport`,
# `--remote-control` and `--from-pr` each touch a session somewhere else and
# none was measured, which is issue #167.
CLOUD_ARGUMENTS = ("--cloud", "--environment")
MEASURED_AGAINST = "claude 2.1.245"


def read_what_leaves_this_machine(
    settings: Path, passthrough: Passthrough
) -> tuple[Reading, ...]:
    """Say what this Claude Code run could send off this machine.

    :param settings: The settings file offgrid writes for this agent.
    :param passthrough: What was handed to the agent unchanged.

    :return: One reading for each way off this machine.

    :raise AgentSettingsError: When the settings are there and cannot be read.
    """
    return (
        _read_hosted_tools(settings, passthrough),
        _read_transcript_sharing(passthrough),
    )


def _read_hosted_tools(settings: Path, passthrough: Passthrough) -> Reading:
    """Say whether WebSearch can still be reached from this run.

    Both halves of it, in the order they bite: an argument that stops the
    settings being loaded leaves them beside the point, however they read.

    :param settings: The settings file offgrid writes for this agent.
    :param passthrough: What was handed to the agent unchanged.

    :return: What it found, and what to change.

    :raise AgentSettingsError: When the settings are there and cannot be read,
        which says nothing either way about WebSearch.
    """
    dropped = get_dropped_settings_sources(passthrough)

    if dropped is not None:
        return Reading(
            subject=Subject.HOSTED_TOOLS,
            status=Status.PERMITTED,
            detail=(
                f"{SOURCES} {','.join(dropped)} does not name "
                f"`{WRITTEN_SOURCE}`, so nothing loads the deny on {SEARCH}."
            ),
            remedy=f"Add `{WRITTEN_SOURCE}` to the list, or drop the argument.",
        )

    # Whether there is anything to read is asked of the text, the same way
    # `configure` asks it. Read off what the text parses to, a file holding
    # `null` would be called empty and answered with the remedy for an empty
    # one — and that remedy is to run the command already running.
    body = read_what_config_is_kept(settings)

    if body is None:
        return Reading(
            subject=Subject.HOSTED_TOOLS,
            status=Status.UNWRITTEN,
            detail=f"{settings} holds nothing, so nothing denies {SEARCH}.",
            remedy="`offgrid run` writes it before it starts the agent.",
        )

    if SEARCH in get_denied_tools(read_as_json(body, settings)):
        return Reading(
            subject=Subject.HOSTED_TOOLS,
            status=Status.DENIED,
            detail=f"{settings} denies {SEARCH}.",
        )

    return Reading(
        subject=Subject.HOSTED_TOOLS,
        status=Status.PERMITTED,
        detail=(
            f"{settings} does not deny {SEARCH}, which runs on Anthropic's "
            "servers: against a local model there is nothing to run it, so "
            "the model invents a result and the agent returns it as an answer."
        ),
        remedy=(
            "Add it to permissions.deny, or delete the file and offgrid writes one."
        ),
    )


def _read_transcript_sharing(passthrough: Passthrough) -> Reading:
    """Say whether this run would send the session to Anthropic's servers.

    :param passthrough: What was handed to the agent unchanged.

    :return: What it found, and what to change.
    """
    asked = [
        argument
        for argument in passthrough
        for flag in CLOUD_ARGUMENTS
        if argument == flag or argument.startswith(f"{flag}=")
    ]

    if not asked:
        return Reading(
            subject=Subject.TRANSCRIPT_SHARING,
            status=Status.DENIED,
            detail=(
                f"Measured against {MEASURED_AGAINST}: neither "
                f"{' nor '.join(f'`{flag}`' for flag in CLOUD_ARGUMENTS)}, which "
                "`--help` says create a session on Anthropic's servers, is here."
            ),
        )

    return Reading(
        subject=Subject.TRANSCRIPT_SHARING,
        status=Status.PERMITTED,
        detail=(
            f"`{asked[0]}` runs this session on Anthropic's servers, so the whole "
            "of it leaves this machine whatever model the profile names."
        ),
        remedy="Drop the argument to run against the model held here.",
    )
