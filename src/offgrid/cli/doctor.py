"""What can be read before a run costs a load."""

import typer

from offgrid.cli.binding import read_what_can_be_read
from offgrid.cli.reporting import reporting
from offgrid.domain.checkup import describe_what_was_read
from offgrid.domain.profile import DEFAULT_PATH
from offgrid.shared.say import tell


def doctor() -> None:
    """Report what the profile, the runtime and the agent each say.

    :raise Exit: With 1 where the runtime is holding no model, which is a
        finding rather than a fault in reaching it, so it is said in the
        report as well.
    """
    with reporting():
        checkup = read_what_can_be_read(DEFAULT_PATH)

    for line in describe_what_was_read(checkup):
        tell(line)

    # The same code every other fault gets, so that a script does not read a
    # report with no model in it as a run that would work.
    if checkup.runtime.resident is None:
        raise typer.Exit(1)
