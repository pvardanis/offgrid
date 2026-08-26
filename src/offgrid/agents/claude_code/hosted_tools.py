"""Whether WebSearch can still be reached from a Claude Code run.

Its own module because it is read in two places at once, neither of which the
sharing reading beside it touches: the settings_path file offgrid writes, and the
argument deciding whether that file is loaded at all.
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


def read_hosted_tools(settings_path: Path, passthrough: Passthrough) -> Reading:
    """Say whether WebSearch can still be reached from this run.

    Both halves of it, in the order they bite: an argument that stops the
    settings_path being loaded leaves them beside the point, however they read.

    :param settings_path: The settings file offgrid writes for this agent.
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
    body = read_what_config_is_kept(settings_path)

    if body is None:
        return Reading(
            subject=Subject.HOSTED_TOOLS,
            status=Status.UNWRITTEN,
            detail=f"{settings_path} holds nothing, so nothing denies {SEARCH}.",
            remedy="`offgrid run` writes it before it starts the agent.",
        )

    if SEARCH in get_denied_tools(read_as_json(body, settings_path)):
        return Reading(
            subject=Subject.HOSTED_TOOLS,
            status=Status.DENIED,
            detail=f"{settings_path} denies {SEARCH}.",
        )

    return Reading(
        subject=Subject.HOSTED_TOOLS,
        status=Status.PERMITTED,
        detail=(
            f"{settings_path} does not deny {SEARCH}, which runs on Anthropic's "
            "servers: against a local model there is nothing to run it, so "
            "the model invents a result and the agent returns it as an answer."
        ),
        remedy=(
            "Add it to permissions.deny, or delete the file and offgrid writes one."
        ),
    )
