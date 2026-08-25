"""What an OpenCode run could send off this machine, read out of what it loads.

One subject is answered from a measurement and one from the file. Every tool
OpenCode offers runs here, so there is nothing hosted to deny; sharing is a key
in `opencode.json`, and `configure` leaves that file alone once it holds an
edit — so a person who edited the key out gets a run that reads it and stops,
which is the only thing left that can tell them.
"""

import json
from pathlib import Path

from offgrid.agents.opencode.configuring import SHARING, SHARING_KEY
from offgrid.domain.running.config_editing import read_as_json, read_what_config_is_kept
from offgrid.domain.running.leaving import Reading, Status, Subject

# What each answer was measured against, so it reads as a fact about a version
# rather than as an adapter whose author never asked the question. Two
# versions, because they are two measurements: naming one of them for both
# would claim a reading nobody took.
#
# The tool list, measured on 2026-08-24 the way `docs/decisions.md` measured
# 1.18.14, by reading the tools it sends — bash, edit, glob, grep, read, skill,
# task, todowrite, webfetch and write, the same ten, every one of them running
# on this machine.
HOSTED_MEASURED_AGAINST = "opencode 1.18.20"

# Sharing, measured on 2026-08-25 with `opencode debug config`, an empty
# configuration and no project configuration read. `share` is absent from what
# it resolves rather than filled in, so a file that does not state it makes no
# claim either way and neither can offgrid.
SHARING_MEASURED_AGAINST = "opencode 1.18.23"


def read_what_leaves_this_machine(settings: Path) -> tuple[Reading, ...]:
    """Say what this OpenCode run could send off this machine.

    :param settings: The configuration file offgrid writes for this agent.

    :return: One reading for each way off this machine.

    :raise AgentSettingsError: When the file is there and cannot be read.
    """
    return (_read_hosted_tools(), _read_transcript_sharing(settings))


def _read_hosted_tools() -> Reading:
    """Say that OpenCode offers no tool offgrid cannot run here.

    :return: That there is nothing to permit, and what that was measured
        against.
    """
    return Reading(
        subject=Subject.HOSTED_TOOLS,
        status=Status.NONE_OFFERED,
        detail=(
            f"Measured against {HOSTED_MEASURED_AGAINST}: every tool it offers runs on "
            "this machine, and it talks to whatever provider it is pointed at "
            "rather than to one vendor, so there is nothing hosted to deny."
        ),
    )


def _read_transcript_sharing(settings: Path) -> Reading:
    """Say whether the file would let a transcript leave this machine.

    Only `disabled` settles it. Anything else the key holds is either sharing
    asked for outright or a value OpenCode does not accept, and neither is a
    promise that a transcript stays here.

    :param settings: The configuration file offgrid writes for this agent.

    :return: What it found, and what to change.

    :raise AgentSettingsError: When the file is there and cannot be read, or
        is not JSON, which says nothing either way about sharing.
    """
    # Asked of the text the same way `configure` asks it, so that the two
    # agree about what nothing in the file means: a file holding `null` is a
    # file `configure` writes into, and answering about it from the parsed
    # value would call it an edit that only a person can finish.
    body = read_what_config_is_kept(settings)

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
    stated = kept.get(SHARING_KEY) if isinstance(kept, dict) else None

    if stated == SHARING:
        return Reading(
            subject=Subject.TRANSCRIPT_SHARING,
            status=Status.DENIED,
            detail=f"{settings} sets `{SHARING_KEY}` to `{SHARING}`.",
        )

    if stated is None:
        return Reading(
            subject=Subject.TRANSCRIPT_SHARING,
            status=Status.UNWRITTEN,
            detail=(
                f"{settings} states no `{SHARING_KEY}`, and measured against "
                f"{SHARING_MEASURED_AGAINST} OpenCode fills in no default for it, so "
                "nothing says whether a transcript leaves this machine. The file "
                "holds an edit, so `offgrid run` will not write into it."
            ),
            remedy=_say_what_to_write(settings),
        )

    return Reading(
        subject=Subject.TRANSCRIPT_SHARING,
        status=Status.PERMITTED,
        # Said back as JSON rather than as Python, because a person is being
        # sent to a JSON file to look at it: `false` is a value they can find
        # in it and `False` is one they cannot.
        detail=(
            f"{settings} sets `{SHARING_KEY}` to {json.dumps(stated)}, which is "
            f"not `{SHARING}`, so a transcript of this run can leave this machine."
        ),
        remedy=_say_what_to_write(settings),
    )


def _say_what_to_write(settings: Path) -> str:
    """Say the edit that settles sharing, and the way out of editing at all.

    :param settings: The configuration file offgrid writes for this agent.

    :return: What to change, in the words the file is written in.
    """
    return (
        f'Set `"{SHARING_KEY}": "{SHARING}"` in {settings}, or delete the file and '
        "offgrid writes one."
    )
