"""The three things offgrid does: describe, check, and launch."""

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import typer

from offgrid.agents.claude_code import dialect as agent_dialect
from offgrid.agents.claude_code import plan, prepare
from offgrid.dialect import require_compatible
from offgrid.exceptions import OffgridError
from offgrid.fit import sizes_that_fit
from offgrid.hold import held, hold, let_go
from offgrid.launch import start
from offgrid.machine import detect
from offgrid.profile import DEFAULT_PATH, Profile, save
from offgrid.profile import load as load_profile
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
    _tell(f"  usable     {machine.usable_bytes / 1e9:.0f}GB")
    _tell("")
    _tell("  A model of about this size fits, leaving room for context:")
    _tell("")
    for bits, parameters in sizes_that_fit(machine):
        _tell(f"    {bits:>2}-bit   {parameters / BILLION:>5.0f}B parameters")
    _tell("")
    _tell(f"  Load one in your runtime, then `offgrid run`. Profile: {DEFAULT_PATH}")

    if limit is None:
        _tell("")
        _tell("  More fits with the GPU limit raised, which a reboot undoes:")
        wanted = int(machine.memory_bytes * 0.875 / (1024 * 1024))
        _tell(f"    sudo sysctl iogpu.wired_limit_mb={wanted}")


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
        # Both of these are knowable before a load, and a load is a minute of
        # someone's time.
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
            _tell(
                f"  Could not start {launch.argv[0]}: {error}. "
                "Install it, or put it on PATH."
            )
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
    except OffgridError as error:
        _tell(f"  {error}")
        _tell("  Writing a fresh profile over it.")
        return None


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
