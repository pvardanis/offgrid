"""The four things offgrid does: describe, check, recommend, and launch."""

import errno
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import typer

from offgrid.agents.claude_code import dialect as agent_dialect
from offgrid.agents.claude_code import plan, prepare
from offgrid.dialect import require_compatible
from offgrid.exceptions import (
    LeaderboardUnavailableError,
    LeaderboardUnreachableError,
    LeaderboardUnreadableError,
    OffgridError,
    ProfileError,
)
from offgrid.fit import BYTES_PER_GB, get_sizes_that_fit
from offgrid.hold import held, hold, let_go
from offgrid.launch import start
from offgrid.leaderboards.cache import Cached, recall, remember
from offgrid.leaderboards.onyx import fetch, parse
from offgrid.listing import Table
from offgrid.machine import detect, suggest_raising_the_gpu_limit
from offgrid.profile import DEFAULT_PATH, Profile, save
from offgrid.profile import load as load_profile
from offgrid.recommendation import summarize_findings
from offgrid.runtimes.lmstudio import dialect as runtime_dialect

CONFIG_DIR = Path.home() / ".offgrid" / "claude-code"
DEFAULT_HOST = "127.0.0.1:1234"
# The local server ignores it; the agent refuses to start without one.
TOKEN = "local"
BILLION = 1e9
GIB = 1024**3

app = typer.Typer(add_completion=False)


@app.callback()
def offgrid() -> None:
    """Run a coding agent against a model on this machine."""
    # This docstring is the help a person reads, so the rest is said here:
    # the callback runs before every command, and is where the command line
    # attaches its own logging. The modules below it attach none.
    _say_on_stderr()


@app.command()
def setup(
    host: str = typer.Option(None, help="Where the runtime listens."),
) -> None:
    """Measure this machine and record how to reach the runtime."""
    machine = detect()
    stored = _stored()
    profile = (
        stored.remeasured(machine, host=host)
        if stored
        else Profile.describing(machine, host=host or DEFAULT_HOST)
    )
    save(profile, DEFAULT_PATH)

    _tell(f"  {machine.chip} · {machine.memory_bytes / GIB:.0f}GB unified memory")
    limit = machine.wired_limit_bytes
    _tell(
        f"  GPU limit  {limit / GIB:.0f}GB" if limit else "  GPU limit  at its default"
    )
    _tell(f"  usable     {machine.usable_bytes / BYTES_PER_GB:.0f}GB")
    _tell("")
    _tell("  A model of about this size fits, leaving room for context:")
    _tell("")
    for bits, parameters in get_sizes_that_fit(machine):
        _tell(f"    {bits:>2}-bit   {parameters / BILLION:>5.0f}B parameters")
    _tell("")
    _tell(f"  Load one in your runtime, then `offgrid run`. Profile: {DEFAULT_PATH}")

    advice = suggest_raising_the_gpu_limit(machine)
    if advice:
        _tell("")
        for line in advice:
            _tell(line)


@app.command()
def doctor() -> None:
    """Check that the runtime is reachable and holding a model."""
    profile = _profile()

    with _reported():
        model = held(profile)

    _tell(f"  runtime   {profile.host} reachable")
    _tell(f"  model     {model.identifier}")
    _tell(f"  context   {model.context_limit or 'unstated'}")
    _tell(f"  agent     {profile.agent}, speaking {agent_dialect().value}")


@app.command()
def recommend() -> None:
    """List the models a published table names that this machine can hold."""
    machine = detect()

    with _reported():
        table = _table()

    for line in summarize_findings(table, machine):
        _tell(line)


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def run(
    context: typer.Context,
    model_name: str = typer.Option(
        None,
        "--model",
        "-m",
        help="Load and use this model instead of the resident one.",
    ),
) -> None:
    """Start the agent against a model the runtime is holding."""
    profile = _profile()
    wanted = model_name or profile.model

    with _reported():
        # A dialect that cannot be paired and settings that would undo a
        # guarantee are both knowable before a load, and a load is tens of
        # seconds nobody gets back.
        require_compatible(runtime_dialect(), agent_dialect())
        prepare(CONFIG_DIR)

        model = hold(profile, wanted) if wanted else held(profile)

    # Nothing between here and the agent finishing may leave the model held:
    # from this line on, letting go is owed whatever happens.
    try:
        _tell(f"  {model.identifier}, context {model.context_limit or 'unstated'}")

        launch = plan(
            model,
            host=profile.host,
            config_dir=CONFIG_DIR,
            token=TOKEN,
            passthrough=list(context.args),
        )

        try:
            code = start(launch)
        except OSError as error:
            _tell(_would_not_start(launch.argv[0], error))
            code = 127
    except KeyboardInterrupt:
        code = 130
    finally:
        let_go(profile.host, model.identifier)

    raise typer.Exit(code)


class _Stderr(logging.StreamHandler):
    """A handler that writes to stderr as it is now.

    A handler that captured the stream it was built on writes into a closed
    buffer once whoever owned that stream is finished with it, and logging
    reports that as a traceback over whatever is being read at the time.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """Write a record to the stream stderr names at this moment.

        :param record: What to write.
        """
        self.stream = sys.stderr
        super().emit(record)


def _say_on_stderr() -> None:
    """Print what offgrid says, as the words and nothing else.

    A library configures no logging; the command line does. It goes to
    stderr so that stdout carries whatever the agent has to say. Only the
    handler this installs is replaced, because a caller that put its own
    there meant it.
    """
    logger = logging.getLogger("offgrid")

    for existing in [h for h in logger.handlers if isinstance(h, _Stderr)]:
        logger.removeHandler(existing)

    handler = _Stderr()
    handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _would_not_start(command: str, error: OSError) -> str:
    """Say what stopped the agent starting, and what to do about that.

    A missing command and a command without the bit that makes it runnable
    fail the same way and are fixed differently, so the advice follows the
    reason rather than the operation.

    :param command: What was being started.
    :param error: Why it was not.

    :return: What to say.
    """
    advice = {
        errno.ENOENT: "Install it, or put it on PATH.",
        errno.EACCES: "It is there but not executable.",
    }.get(error.errno, "")

    return f"  Could not start {command}: {error}. {advice}".rstrip()


def _tell(message: str) -> None:
    """Say something to whoever is running offgrid.

    :param message: What to say.
    """
    typer.echo(message, err=True)


@contextmanager
def _reported() -> Iterator[None]:
    """Say what went wrong and stop, rather than raising at the terminal.

    offgrid's own errors carry the operation, the input and what to do next,
    which a traceback buries.

    :yield: To the operation being run.
    """
    try:
        yield
    except OffgridError as error:
        _tell(f"  {error}")
        raise typer.Exit(1) from error


def _stored() -> Profile | None:
    """Read the profile already there, so a re-run does not undo an edit.

    :return: The stored profile, or ``None`` when there is none to keep.
    """
    if not DEFAULT_PATH.exists():
        return None

    try:
        return load_profile(DEFAULT_PATH)
    except ProfileError as error:
        kept = DEFAULT_PATH.with_suffix(".yaml.rejected")
        kept.write_text(DEFAULT_PATH.read_text())

        _tell(f"  {error}")
        _tell(f"  What was there is at {kept}. Writing a fresh profile.")
        return None


def _table() -> Table:
    """Read the published list, falling back on the last one that was read.

    :return: The table to recommend from.

    :raise LeaderboardUnavailableError: When nothing answered and there is no
        table kept from a run that reached one.
    """
    try:
        payload = fetch()
    except LeaderboardUnreachableError as error:
        return _last_table(error)

    try:
        table = parse(payload)
    except LeaderboardUnreadableError as error:
        return _last_table(error)

    remember(payload, _cache())

    return table


def _last_table(reason: LeaderboardUnavailableError) -> Table:
    """Read back the last table offgrid fetched, and say how old it is.

    What stopped this run is said either way. A page that has been rewritten
    has to be loud even where a kept table saves the answer, and a network
    that is not there has to be named so that nobody goes looking for a fault
    on this machine.

    :param reason: What stopped this run reading a current one.

    :return: The table as it stood when it was last read.

    :raise LeaderboardUnavailableError: When there is no kept table to fall
        back on. Nothing was read and nothing was kept, so what is left to
        say is where numbers measured on this machine already are.
    """
    kept = recall(_cache())
    table = _reparsed(kept)

    if kept is None or table is None:
        raise LeaderboardUnavailableError(
            f"{reason} No table was kept by an earlier run either, so there "
            "is none to fall back on. docs/models.md holds what has been "
            "measured on this machine by hand."
        ) from reason

    _tell(f"  {reason}")
    _tell(f"  This is the table offgrid read on {kept.dated}, not a current one.")
    _tell("")

    return table


def _reparsed(kept: Cached | None) -> Table | None:
    """Read a kept payload the way the one it was kept from was read.

    :param kept: What was kept, if anything was.

    :return: The table it holds, or ``None`` where it holds none. A payload
        kept before the parser knew what it knows now is no table, and this
        run already has a failure to report.
    """
    if kept is None:
        return None

    try:
        return parse(kept.payload)
    except LeaderboardUnreadableError:
        return None


def _cache() -> Path:
    """Where the last table read is kept, beside the profile.

    :return: The path to it.
    """
    return DEFAULT_PATH.parent / "leaderboard.json"


def _profile() -> Profile:
    """Read the stored profile, or explain how to make one.

    :return: The stored profile.
    """
    with _reported():
        return load_profile(DEFAULT_PATH)


def main() -> None:
    """Run the command line, reporting offgrid's own errors as messages.

    A command reports what it can itself. This is the net under everything
    else, so an error offgrid raised on purpose reaches the terminal as the
    sentence it was written as rather than as a traceback.
    """
    try:
        app()
    except OffgridError as error:
        _tell(f"  {error}")
        sys.exit(1)
