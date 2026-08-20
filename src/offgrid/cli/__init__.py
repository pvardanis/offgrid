"""The four things offgrid does: describe, check, recommend, and launch.

One module per command, and this is where each is attached to the command
line. A command is a plain function in the module named after it, so what a
command does can be read without the wiring around it, and the wiring can be
read in one place.
"""

import sys

import typer

# The modules rather than the functions in them: each is named after the
# command it holds, so importing the function would rebind the name here from
# the module to what is inside it — and a command's own name would no longer
# reach the module a test patches or a reader opens.
from offgrid.cli import doctor, recommend, run, setup
from offgrid.shared.exceptions import OffgridError
from offgrid.shared.say import say_on_stderr, tell

__all__ = ["app", "main"]

app = typer.Typer(add_completion=False)


@app.callback()
def offgrid() -> None:
    """Run a coding agent against a model on this machine."""
    # This docstring is the help a person reads, so the rest is said here:
    # the callback runs before every command, and is where the command line
    # attaches its own logging. The modules below it attach none.
    say_on_stderr()


app.command()(setup.setup)
app.command()(doctor.doctor)
app.command()(recommend.recommend)
app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)(run.run)


def main() -> None:
    """Run the command line, reporting offgrid's own errors as messages.

    A command reports what it can itself. This is the net under everything
    else, so an error offgrid raised on purpose reaches the terminal as the
    sentence it was written as rather than as a traceback.
    """
    try:
        app()
    except OffgridError as error:
        tell(f"  {error}")
        sys.exit(1)
