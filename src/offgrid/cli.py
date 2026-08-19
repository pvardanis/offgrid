"""The four things offgrid does: describe, check, recommend, and launch."""

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import typer

from offgrid.agents import create_agent_config
from offgrid.binding import bind_run, read_profile
from offgrid.domain.profile import DEFAULT_PATH, Profile, save_profile
from offgrid.domain.running.agent import AgentName
from offgrid.domain.running.answering import get_resident_model, hold_model
from offgrid.domain.running.dialect import require_compatible
from offgrid.domain.running.hosted_tools import (
    HostedToolsStatus,
    require_hosted_tools_denied,
)
from offgrid.domain.running.launch import explain_why_it_would_not_start, start
from offgrid.domain.running.model import ModelRequest
from offgrid.domain.running.runtime import RuntimeName
from offgrid.domain.sizing.fit import BYTES_PER_GB, get_sizes_that_fit
from offgrid.domain.sizing.machine import detect, suggest_raising_the_gpu_limit
from offgrid.domain.sizing.reading import get_reading
from offgrid.domain.sizing.recommendation import summarize_findings
from offgrid.leaderboards import LEADERBOARDS
from offgrid.runtimes import create_runtime_config
from offgrid.shared.exceptions import OffgridError, ProfileError
from offgrid.shared.say import say_on_stderr, tell

DEFAULT_HOST = "127.0.0.1:1234"
# What a fresh profile names. Which adapter to write down is this command's
# decision, not something the file may leave out and have guessed for it.
DEFAULT_RUNTIME = RuntimeName.LMSTUDIO
DEFAULT_AGENT = AgentName.CLAUDE_CODE
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
    stored = _get_stored_profile()
    listening_at = host or (stored.runtime.host if stored else DEFAULT_HOST)

    # What was stored is carried over whole rather than rebuilt from the
    # defaults, so a re-run keeps the adapters named and whatever settings of
    # their own they were given. Only the address moves, and it moves in both
    # places at once.
    with _reporting():
        runtime = (
            stored.runtime.model_copy(update={"host": listening_at})
            if stored
            else create_runtime_config(
                {"name": DEFAULT_RUNTIME.value, "host": listening_at}
            )
        )
        agent = (
            stored.agent.model_copy(update={"runtime_host": listening_at})
            if stored
            else create_agent_config(
                {"name": DEFAULT_AGENT.value}, runtime_host=listening_at
            )
        )

    save_profile(
        Profile(runtime=runtime, agent=agent, model=stored.model if stored else None),
        DEFAULT_PATH,
    )

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
    tell("  `offgrid recommend` names the published models that fit.")
    tell(f"  Load one in your runtime, then `offgrid run`. Profile: {DEFAULT_PATH}")

    advice = suggest_raising_the_gpu_limit(machine)
    if advice:
        tell("")
        for line in advice:
            tell(line)


@app.command()
def doctor() -> None:
    """Check that the runtime is reachable and holding a model."""
    # Reading, binding and both askings happen before anything is printed, so
    # a fault in any of them is reported as offgrid's own error rather than as
    # a traceback under four lines that already looked like an answer.
    with _reporting():
        profile, runtime, agent = bind_run(DEFAULT_PATH)

        model = get_resident_model(runtime)
        report = agent.read_hosted_tools()

    tell(
        f"  runtime   {profile.runtime.name.value} at {profile.runtime.host}, reachable"
    )
    tell(f"  model     {model.identifier}")
    tell(f"  ceiling   {model.context_ceiling or 'unstated'}")
    tell(f"  window    {model.context_window or 'unstated'}")
    tell(f"  agent     {profile.agent.name.value}, speaking {agent.dialect.value}")
    tell(f"  floor     {agent.context_floor}")
    tell(f"  hosted    {report.status}")

    # What a run would refuse with, said here instead of after the load it
    # was run to save. Nothing to act on where nothing can be reached.
    if report.status is not HostedToolsStatus.DENIED:
        tell(f"            {report.detail} {report.remedy}".rstrip())


@app.command()
def recommend() -> None:
    """List the models a published table names that this machine can hold."""
    machine = detect()

    with _reporting():
        reading = get_reading(LEADERBOARDS, _cache())

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
    context_window: int = typer.Option(
        None,
        "--context-window",
        min=1,
        help="Hold the model at this window. Left out, the runtime's own is used.",
    ),
) -> None:
    """Start the agent against a model the runtime is holding."""
    passthrough = tuple(context.args)

    with _reporting():
        profile, runtime, agent = bind_run(DEFAULT_PATH, passthrough)
        model_request = ModelRequest(
            identifier=model_name or profile.model,
            context_window=context_window,
        )

        # A dialect that cannot be paired, a run that would undo a guarantee
        # and a window nothing could serve are all knowable before a load, and
        # a load is tens of seconds nobody gets back.
        require_compatible(runtime.dialect, agent.dialect)
        agent.configure()
        require_hosted_tools_denied(agent.read_hosted_tools())

        model = hold_model(runtime, model_request, context_floor=agent.context_floor)

    # Nothing between here and the agent finishing may leave the model held:
    # from this line on, letting go is owed whatever happens.
    try:
        tell(f"  {model.identifier}, window {model.context_window or 'unstated'}")

        launch = agent.plan(model)
        # Said whenever there is anything at all, so an agent answering with
        # an empty one shows as a blank line somebody reports rather than as
        # a warning nobody was given.
        if launch.caution is not None:
            tell(f"  {launch.caution}")

        try:
            code = start(launch)
        except OSError as error:
            tell(explain_why_it_would_not_start(launch.argv[0], error))
            code = 127
    except KeyboardInterrupt:
        code = 130
    finally:
        runtime.let_go(model.identifier)

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


def _get_stored_profile() -> Profile | None:
    """Read the profile already there, so a re-run does not undo an edit.

    :return: The stored profile, or ``None`` when there is none to keep.
    """
    if not DEFAULT_PATH.exists():
        return None

    try:
        return read_profile(DEFAULT_PATH)
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
