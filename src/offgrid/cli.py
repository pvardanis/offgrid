"""The four things offgrid does: describe, check, recommend, and launch."""

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import typer

from offgrid.agents.claude_code import dialect as agent_dialect
from offgrid.agents.claude_code import plan, prepare
from offgrid.dialect import require_compatible
from offgrid.exceptions import OffgridError, ProfileError
from offgrid.fit import BYTES_PER_GB, get_sizes_that_fit
from offgrid.hold import held, hold, let_go
from offgrid.launch import explain_why_it_would_not_start, start
from offgrid.leaderboards.reading import get_reading
from offgrid.machine import detect, suggest_raising_the_gpu_limit
from offgrid.profile import DEFAULT_PATH, Profile, save
from offgrid.profile import load as load_profile
from offgrid.recommendation import summarize_findings
from offgrid.runtimes.lmstudio import dialect as runtime_dialect
from offgrid.say import say_on_stderr, tell

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
    say_on_stderr()


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

    tell(f"  {machine.chip} · {machine.memory_bytes / GIB:.0f}GB unified memory")
    limit = machine.wired_limit_bytes
    tell(
        f"  GPU limit  {limit / GIB:.0f}GB" if limit else "  GPU limit  at its default"
    )
    tell(f"  usable     {machine.usable_bytes / BYTES_PER_GB:.0f}GB")
    tell("")
    tell("  A model of about this size fits, leaving room for context:")
    tell("")
    for bits, parameters in get_sizes_that_fit(machine):
        tell(f"    {bits:>2}-bit   {parameters / BILLION:>5.0f}B parameters")
    tell("")
    tell(f"  Load one in your runtime, then `offgrid run`. Profile: {DEFAULT_PATH}")

    advice = suggest_raising_the_gpu_limit(machine)
    if advice:
        tell("")
        for line in advice:
            tell(line)


@app.command()
def doctor() -> None:
    """Check that the runtime is reachable and holding a model."""
    profile = _profile()

    with _reporting():
        model = held(profile)

    tell(f"  runtime   {profile.host} reachable")
    tell(f"  model     {model.identifier}")
    tell(f"  context   {model.context_limit or 'unstated'}")
    tell(f"  agent     {profile.agent}, speaking {agent_dialect().value}")


@app.command()
def recommend() -> None:
    """List the models a published table names that this machine can hold."""
    machine = detect()

    with _reporting():
        reading = get_reading(_cache())

    for line in reading.caveats:
        tell(line)

    for line in summarize_findings(reading.table, machine):
        tell(line)


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

    with _reporting():
        # A dialect that cannot be paired and settings that would undo a
        # guarantee are both knowable before a load, and a load is tens of
        # seconds nobody gets back.
        require_compatible(runtime_dialect(), agent_dialect())
        prepare(CONFIG_DIR)

        model = hold(profile, wanted) if wanted else held(profile)

    # Nothing between here and the agent finishing may leave the model held:
    # from this line on, letting go is owed whatever happens.
    try:
        tell(f"  {model.identifier}, context {model.context_limit or 'unstated'}")

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
            tell(explain_why_it_would_not_start(launch.argv[0], error))
            code = 127
    except KeyboardInterrupt:
        code = 130
    finally:
        let_go(profile.host, model.identifier)

    raise typer.Exit(code)


@contextmanager
def _reporting() -> Iterator[None]:
    """Say what went wrong and stop, rather than raising at the terminal.

    offgrid's own errors carry the operation, the input and what to do next,
    which a traceback buries.

    :yield: To the operation being run.
    """
    try:
        yield
    except OffgridError as error:
        tell(f"  {error}")
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

        tell(f"  {error}")
        tell(f"  What was there is at {kept}. Writing a fresh profile.")
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
    with _reporting():
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
        tell(f"  {error}")
        sys.exit(1)
