"""What can be read before a run costs a load."""

import typer

from offgrid.cli.binding import bind_run
from offgrid.cli.reporting import reporting
from offgrid.domain.checkup import (
    Checkup,
    WhatTheAgentAnswered,
    WhatTheRuntimeAnswered,
    describe_what_was_read,
)
from offgrid.domain.profile import DEFAULT_PATH, Profile
from offgrid.domain.running import discarded_windows
from offgrid.domain.running.agent_presence import find_agent_on_path
from offgrid.domain.running.answering import find_resident_model
from offgrid.domain.running.discarded_windows import DiscardedWindow
from offgrid.domain.running.model import Model
from offgrid.shared.exceptions import DiscardedWindowsUnreadableError
from offgrid.shared.say import tell


def doctor() -> None:
    """Report what the profile, the runtime and the agent each say.

    :raise Exit: With 1 where the runtime is holding no model, which is a
        finding rather than a fault in reaching it, so it is said in the
        report as well.
    """
    # Everything is read before anything is said, so a fault in any of it is
    # reported as offgrid's own error rather than as a traceback under lines
    # that already looked like an answer.
    checkup = _read_what_can_be_read()

    for line in describe_what_was_read(checkup):
        tell(line)

    # The same code every other fault gets, so that a script does not read a
    # report with no model in it as a run that would work.
    if checkup.runtime.resident is None:
        raise typer.Exit(1)


@reporting()
def _read_what_can_be_read() -> Checkup:
    """Ask the profile, the runtime and the agent what each of them says.

    :return: What each of them answered.
    """
    profile, runtime, agent = bind_run(DEFAULT_PATH)

    resident = find_resident_model(runtime)
    discarded, unreadable = _read_what_was_discarded(profile, resident)

    agent_terms = agent.terms

    return Checkup(
        profile=profile,
        runtime=WhatTheRuntimeAnswered(
            resident=resident,
            served=runtime.dialects,
            discarded=discarded,
            unreadable=unreadable,
        ),
        agent=WhatTheAgentAnswered(
            terms=agent_terms,
            found_at=find_agent_on_path(agent_terms.command),
            could_leave=agent.read_what_leaves_this_machine(),
            kept=agent.conversations,
        ),
    )


def _read_what_was_discarded(
    profile: Profile, resident: Model | None
) -> tuple[tuple[DiscardedWindow, ...], str | None]:
    """Read the windows this runtime discarded for the model it is holding.

    A file that will not read is a finding rather than a fault here. Every
    other reading in the report succeeded, and refusing to say any of them
    over a record offgrid keeps for itself would answer a person who ran
    `doctor` because something is wrong with one line about a file they have
    never heard of.

    :param profile: What was written down.
    :param resident: The model the runtime is holding, or ``None`` for none.

    :return: Every window it discarded for that model, and why the records
        could not be read where they could not.
    """
    if resident is None:
        return (), None

    try:
        records = discarded_windows.read_discarded_windows(
            profile.runtime.name, profile.runtime.host, discarded_windows.DEFAULT_PATH
        )
    except DiscardedWindowsUnreadableError as error:
        return (), str(error)

    return tuple(r for r in records if r.identifier == resident.identifier), None
