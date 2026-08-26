"""Whether an OpenCode run could publish a transcript of itself.

Two places decide it and the command line is the first, the way
`--setting-sources` comes before the settings it stops being read: a file
saying `disabled` says nothing about a run that asks to share on the way past.
"""

import json
from pathlib import Path

from offgrid.agents.opencode.configuring import SHARING, SHARING_KEY
from offgrid.domain.running.agent import Passthrough
from offgrid.domain.running.config_editing import read_as_json, read_what_config_is_kept
from offgrid.domain.running.leaving import Reading, Status, Subject

# What `opencode run --help` offers at the version below: `--share`, "share the
# session". A flag on the subcommand rather than a setting, so no reading of
# the file can see it, and `run` hands the whole command line through. Whether
# it beats `"share": "disabled"` was deliberately not measured, because
# measuring it means publishing a real session — offgrid does not need to know,
# since it cannot promise a transcript stays here while an argument asks for
# one, so the run stops either way and names the argument.
SHARING_ARGUMENT = "--share"
MEASURED_AGAINST = "opencode 1.18.23"

_SETTLED = f'`"{SHARING_KEY}": "{SHARING}"`'
"""The edit that settles sharing, spelled the way the file spells it."""


def read_transcript_sharing(settings: Path, passthrough: Passthrough) -> Reading:
    """Say whether this run could let a transcript leave this machine.

    :param settings: The configuration file offgrid writes for this agent.
    :param passthrough: What was handed to the agent unchanged.

    :return: What it found, and what to change.

    :raise AgentSettingsError: When the file is there and cannot be read.
    """
    asked = _read_the_argument(passthrough)

    if asked is not None:
        return Reading(
            subject=Subject.TRANSCRIPT_SHARING,
            status=Status.PERMITTED,
            detail=(
                f"`{asked}` asks OpenCode to share the session, and no "
                f"`{SHARING_KEY}` in a file is a promise about a run that asks "
                "for it on the command line."
            ),
            remedy="Drop the argument to keep the transcript on this machine.",
        )

    return _read_the_file(settings)


def _read_the_argument(passthrough: Passthrough) -> str | None:
    """Pick out an argument asking OpenCode to share the session.

    Matched at the start of an argument, so a prompt quoting the flag does not
    count as typing it, and `--no-share` matches neither spelling.

    :param passthrough: What was handed to the agent unchanged.

    :return: The argument, or nothing where none asks.
    """
    asking = (
        argument
        for argument in passthrough
        if argument == SHARING_ARGUMENT or argument.startswith(f"{SHARING_ARGUMENT}=")
    )

    return next(asking, None)


def _read_the_file(settings: Path) -> Reading:
    """Say what the configuration settles about sharing, where anything does.

    Only `disabled` settles it. A file that is not an object, and one stating
    the key as `null`, each say so in their own words, because the remedy has
    to match what is in front of the person.

    :param settings: The configuration file offgrid writes for this agent.

    :return: What it found, and what to change.

    :raise AgentSettingsError: When it cannot be read, or is not JSON.
    """
    body = read_what_config_is_kept(settings)
    edit = f"Set {_SETTLED} in {settings}, or delete the file and offgrid writes one."

    if body is None:
        return Reading(
            subject=Subject.TRANSCRIPT_SHARING,
            status=Status.UNWRITTEN,
            detail=(
                f"{settings} holds nothing, so nothing says whether a transcript "
                "leaves this machine."
            ),
            remedy="`offgrid run` writes it before it starts the agent.",
        )

    kept = read_as_json(body, settings)

    if not isinstance(kept, dict):
        return Reading(
            subject=Subject.TRANSCRIPT_SHARING,
            status=Status.UNWRITTEN,
            detail=(
                f"{settings} holds {type(kept).__name__} rather than an object, so "
                f"there is no `{SHARING_KEY}` in it to read, and OpenCode loads no "
                "configuration out of it either."
            ),
            remedy=f"Replace it with an object stating {_SETTLED}, or delete it.",
        )

    stated = kept.get(SHARING_KEY)

    if stated == SHARING:
        return Reading(
            subject=Subject.TRANSCRIPT_SHARING,
            status=Status.DENIED,
            detail=f"{settings} sets `{SHARING_KEY}` to `{SHARING}`.",
        )

    if SHARING_KEY not in kept:
        return Reading(
            subject=Subject.TRANSCRIPT_SHARING,
            status=Status.UNWRITTEN,
            detail=(
                f"{settings} states no `{SHARING_KEY}`, and measured against "
                f"{MEASURED_AGAINST} OpenCode fills in no default for it, so "
                "nothing says whether a transcript leaves this machine. The file "
                "holds an edit, so `offgrid run` will not write into it."
            ),
            remedy=edit,
        )

    # Said back as JSON rather than as Python, because a person is being sent to
    # a JSON file to look at it: `false` is in it and `False` is not.
    return Reading(
        subject=Subject.TRANSCRIPT_SHARING,
        status=Status.PERMITTED,
        detail=(
            f"{settings} sets `{SHARING_KEY}` to {json.dumps(stated)}, which is "
            f"not `{SHARING}`, so a transcript of this run can leave this machine."
        ),
        remedy=edit,
    )
