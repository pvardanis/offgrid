"""The four things offgrid does: describe, check, recommend, and launch.

One module per command, and this is where each is attached to the command
line. A command is a plain function in the module named after it, so what a
command does can be read without the wiring around it, and the wiring can be
read in one place.
"""

import sys

import typer

# Under a second name, because each module is named after the command it
# holds: binding `setup` here would rebind it from the module to the function
# inside it, and `offgrid.cli.setup` would stop reaching the module a test
# patches or a reader opens. Importing the submodule is what puts the module
# there; only the name this file binds is the alias.
from offgrid.cli.binding import read_what_can_be_read
from offgrid.cli.doctor import doctor as doctor_command
from offgrid.cli.recommend import recommend as recommend_command
from offgrid.cli.run import run as run_command
from offgrid.cli.setup import setup as setup_command
from offgrid.domain.profile import DEFAULT_PATH
from offgrid.shared.exceptions import OffgridError
from offgrid.shared.say import say_on_stderr, tell

__all__ = ["app", "main"]

app = typer.Typer(add_completion=False)


@app.callback(invoke_without_command=True)
def offgrid(ctx: typer.Context) -> None:
    """Run a coding agent against a model on this machine."""
    # This docstring is the help a person reads, so the rest is said here:
    # the callback runs before every command, and is where the command line
    # attaches its own logging. The modules below it attach none.
    say_on_stderr()

    # Named with nothing to do, offgrid shows what it knows rather than the
    # command table, which is the least useful thing a stranger can be shown.
    # The screen is handed its reading, so that the picker names no registry.
    if ctx.invoked_subcommand is None:
        # Imported here rather than above: Textual costs an order of
        # magnitude more to import than the command line's own toolkit, and
        # every command that is not the screen would pay it.
        from offgrid.tui.picker import Report

        Report(read=lambda: read_what_can_be_read(DEFAULT_PATH)).run()


app.command()(setup_command)
app.command()(doctor_command)
app.command()(recommend_command)
app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)(run_command)


def main() -> None:
    """Run the command line, reporting offgrid's own errors as messages.

    A command reports what it can itself. This is the net under everything
    else, so an error offgrid raised on purpose reaches the terminal as the
    sentence it was written as rather than as a traceback.
    """
    try:
        app()
    except OffgridError as error:
        tell(f"{error}")
        sys.exit(1)
