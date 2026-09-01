"""The five things offgrid does: describe, check, recommend, launch, and show.

One module per command, and this is where each is attached to the command
line. A command is a plain function in the module named after it, so what a
command does can be read without the wiring around it, and the wiring can be
read in one place.

Showing is the one with no command of its own: it is what offgrid named with
nothing to do does, so it lives in the callback that runs before every
command rather than beside the four.
"""

import logging
import subprocess
import sys
from pathlib import Path

import typer

# Under a second name, because each module is named after the command it
# holds: binding `setup` here would rebind it from the module to the function
# inside it, and `offgrid.cli.setup` would stop reaching the module a test
# patches or a reader opens. Importing the submodule is what puts the module
# there; only the name this file binds is the alias.
from offgrid.cli.binding import read_what_could_be_run, there_is_no_profile
from offgrid.cli.doctor import doctor as doctor_command
from offgrid.cli.recommend import read_what_a_list_recommends
from offgrid.cli.recommend import recommend as recommend_command
from offgrid.cli.run import launch_the_assembled_profile
from offgrid.cli.run import run as run_command
from offgrid.cli.setup import setup as setup_command
from offgrid.domain.profile import DEFAULT_PATH, save_profile
from offgrid.domain.sizing.machine import detect
from offgrid.domain.sizing.measuring import describe_the_machine_and_how_to_fit_more
from offgrid.shared.exceptions import OffgridError
from offgrid.shared.say import LOGGER, say_on_stderr, someone_is_at_a_terminal, tell

__all__ = ["app", "main"]

app = typer.Typer(add_completion=False)


def read_this_build() -> str:
    """Read the short commit of the offgrid checkout this is running from.

    A git SHA rather than a version: there is no published package to name, and
    a person running several clones needs to know which one is about to run. It
    is read against the source tree this file sits in, not the shell's cwd, so
    it names the offgrid whose code is running rather than whatever repository a
    run happens to start in.

    :return: The short SHA, or ``unknown`` where git cannot answer — not a
        checkout, or no git on the ``PATH``. The header only displays it, so a
        missing SHA is a word rather than a refusal that would keep the screen
        from opening. The benign misses stay quiet; where git ran against a
        checkout and refused with something to say, what it said is logged at
        warning level, so an ``unknown`` on a real checkout is not silent.
    """
    source = Path(__file__).resolve().parent.parent

    log = logging.getLogger(LOGGER)

    try:
        found = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        log.debug("Could not run git to read the build: %s", error)

        return "unknown"

    sha = found.stdout.strip()

    if sha:
        return sha

    # A git that ran, exited non-zero and said why is a checkout it refused to
    # name — a broken HEAD, a permissions problem — which the debug level would
    # bury below the handler the command line installs. A run that named no
    # commit and said nothing is the benign miss, and stays quiet.
    if found.returncode != 0 and found.stderr.strip():
        log.warning(
            "git could not name this build's commit for %s (exit %s): %s",
            source,
            found.returncode,
            found.stderr.strip(),
        )

    return "unknown"


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
    from offgrid.tui.picker import Picker

    # A stranger following the README has written no profile, and the screen
    # measures the machine for them rather than sending them to `setup` first.
    # A file that is there is a run already assembled, and its budget is not
    # what its owner opened the screen to read — so nothing is measured for it.
    def measure() -> tuple[str, ...]:
        return describe_the_machine_and_how_to_fit_more(detect())

    screen = Picker(
        read_report_func=lambda: read_what_could_be_run(DEFAULT_PATH),
        save_func=lambda profile: save_profile(profile, DEFAULT_PATH),
        sha=read_this_build(),
        cwd=str(Path.cwd()),
        measure_func=measure if there_is_no_profile(DEFAULT_PATH) else None,
        recommend_func=read_what_a_list_recommends,
    )
    departure = screen.run()

    # Textual paints what went wrong on the screen and returns rather than
    # raising it, so the code it set is the only thing that says the screen
    # died. Unread, a crash under a traceback exits like a report somebody
    # sat and read.
    if screen.return_code:
        raise typer.Exit(screen.return_code)

    # A key that ends the session hands back what to run; `q` hands back
    # nothing. The run is carried out here, in the plain lines a run is read
    # in, rather than on the screen, which is gone by now.
    if departure is not None:
        launch_the_assembled_profile(departure.profile, saved=departure.saved)


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
