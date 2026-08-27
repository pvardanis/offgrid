"""The five things offgrid does: describe, check, recommend, launch, and show.

One module per command, and this is where each is attached to the command
line. A command is a plain function in the module named after it, so what a
command does can be read without the wiring around it, and the wiring can be
read in one place.

Showing is the one with no command of its own: it is what offgrid named with
nothing to do does, so it lives in the callback that runs before every
command rather than beside the four.
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
from offgrid.shared.say import say_on_stderr, someone_is_at_a_terminal, tell

__all__ = ["app", "main"]

app = typer.Typer(add_completion=False)


@app.callback(invoke_without_command=True)
def offgrid(ctx: typer.Context) -> None:
    """Run a coding agent against a model on this machine."""
    # This docstring is the help a person reads, so the rest is said here:
    # the callback runs before every command, and is where the command line
    # attaches its own logging. The modules below it attach none.
    say_on_stderr()

    if ctx.invoked_subcommand is not None:
        return

    # Somewhere with nobody at it, the command table is what there is to say:
    # a screen would take the terminal and wait for a key that never arrives,
    # which is a script that never returns and a log full of escape codes.
    if not someone_is_at_a_terminal():
        # Typer renders the help through a console of its own and answers with
        # nothing, so asking for it is what prints it.
        ctx.get_help()

        return

    # Named with nothing to do, offgrid shows what it knows rather than the
    # command table, which is the least useful thing a stranger can be shown.
    # The screen is handed its reading, so that the picker names no registry.
    #
    # Imported here rather than above: Textual costs an order of magnitude
    # more to import than the command line's own toolkit, and every command
    # that is not the screen would pay it.
    from offgrid.tui.picker import Report

    screen = Report(read=lambda: read_what_can_be_read(DEFAULT_PATH))
    screen.run()

    # Textual paints what went wrong on the screen and returns rather than
    # raising it, so the code it set is the only thing that says the screen
    # died. Unread, a crash under a traceback exits like a report somebody
    # sat and read.
    if screen.return_code:
        raise typer.Exit(screen.return_code)


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
