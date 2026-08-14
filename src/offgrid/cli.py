"""The four things offgrid does: describe, check, recommend, and launch."""

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import typer

from offgrid.agent import AgentName
from offgrid.agents import create_agent_config, prepare_agent
from offgrid.answering import get_resident_model, hold_model
from offgrid.dialect import require_compatible
from offgrid.exceptions import OffgridError, ProfileError
from offgrid.fit import BYTES_PER_GB, get_sizes_that_fit
from offgrid.hosted_tools import HostedToolsStatus, require_hosted_tools_denied
from offgrid.launch import explain_why_it_would_not_start, start
from offgrid.leaderboards.reading import get_reading
from offgrid.machine import detect, suggest_raising_the_gpu_limit
from offgrid.profile import (
    DEFAULT_PATH,
    Profile,
    create_profile,
    load_yaml,
    refusing,
    save,
)
from offgrid.recommendation import summarize_findings
from offgrid.runtime import RuntimeName
from offgrid.runtimes import connect_runtime, create_runtime_config
from offgrid.say import say_on_stderr, tell

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
    profile = _stored()
    listening_at = host or (profile.runtime.host if profile else DEFAULT_HOST)

    with _reporting():
        runtime = create_runtime_config(
            {"name": DEFAULT_RUNTIME.value, "host": listening_at}
        )
        agent = create_agent_config(
            {"name": DEFAULT_AGENT.value}, runtime_host=listening_at
        )

    save(
        Profile(runtime=runtime, agent=agent, model=profile.model if profile else None),
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
        profile = read_profile(DEFAULT_PATH)

        runtime = connect_runtime(profile.runtime)
        agent = prepare_agent(profile.agent)

        model = get_resident_model(runtime)
        report = agent.read_hosted_tools()

    tell(
        f"  runtime   {profile.runtime.name.value} at {profile.runtime.host}, reachable"
    )
    tell(f"  model     {model.identifier}")
    tell(f"  context   {model.context_limit or 'unstated'}")
    tell(f"  agent     {profile.agent.name.value}, speaking {agent.dialect.value}")
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
    passthrough = tuple(context.args)

    with _reporting():
        profile = read_profile(DEFAULT_PATH)
        wanted = model_name or profile.model

        runtime = connect_runtime(profile.runtime)
        agent = prepare_agent(profile.agent, passthrough)

        # A dialect that cannot be paired and a run that would undo a
        # guarantee are both knowable before a load, and a load is tens of
        # seconds nobody gets back.
        require_compatible(runtime.dialect, agent.dialect)
        agent.configure()
        require_hosted_tools_denied(agent.read_hosted_tools())

        model = hold_model(runtime, wanted)

    # Nothing between here and the agent finishing may leave the model held:
    # from this line on, letting go is owed whatever happens.
    try:
        tell(f"  {model.identifier}, context {model.context_limit or 'unstated'}")

        launch = agent.plan(model)

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


def _stored() -> Profile | None:
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


def read_profile(path: Path) -> Profile:
    """Read a profile, asking each registry to read the section that is its own.

    This is the one place that has both registries, so it is the one place a
    section can become the config an adapter is built from.

    :param path: Where to read it from.

    :return: What a run is made from.

    :raise ProfileError: When the file is not one, or a section is not one its
        adapter can read.
    """
    body = load_yaml(path)
    said = {port: body.get(port, {}) for port in ("runtime", "agent")}

    with refusing(said["runtime"], port="runtime", names=RuntimeName):
        runtime = create_runtime_config(said["runtime"])

    with refusing(said["agent"], port="agent", names=AgentName):
        agent = create_agent_config(said["agent"], runtime_host=runtime.host)

    return create_profile(body, runtime=runtime, agent=agent)


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
