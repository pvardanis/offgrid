"""The three things offgrid does: describe, check, and launch."""

import os
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import typer

from offgrid.agents.claude_code import Launch, plan, prepare
from offgrid.agents.claude_code import dialect as agent_dialect
from offgrid.dialect import require_compatible
from offgrid.exceptions import OffgridError
from offgrid.fit import sizes_that_fit
from offgrid.machine import detect
from offgrid.model import Model
from offgrid.profile import DEFAULT_PATH, Profile, save
from offgrid.profile import load as load_profile
from offgrid.runtimes.lmstudio import catalogue, loaded, parse_models, resident, unload
from offgrid.runtimes.lmstudio import dialect as runtime_dialect
from offgrid.runtimes.lmstudio import load as load_model

CONFIG_DIR = Path.home() / ".offgrid" / "claude-code"
DEFAULT_HOST = "127.0.0.1:1234"
# The local server ignores it; the agent refuses to start without one.
TOKEN = "local"
BILLION = 1e9
GIB = 1024**3

# Being stopped by either of these means offgrid is going away, and the agent
# has to go with it rather than outlive the model it is talking to.
STOPS = (signal.SIGTERM, signal.SIGHUP)

app = typer.Typer(
    help="Run a coding agent against a model on this machine.", add_completion=False
)


@app.command()
def setup(
    host: str = typer.Option(DEFAULT_HOST, help="Where the runtime listens."),
) -> None:
    """Measure this machine and record how to reach the runtime."""
    machine = detect()
    profile = Profile.describing(machine, host=host)
    save(profile, DEFAULT_PATH)

    typer.echo(f"  {machine.chip} · {machine.memory_bytes / GIB:.0f}GB unified memory")
    limit = machine.wired_limit_bytes
    typer.echo(
        f"  GPU limit  {limit / GIB:.0f}GB" if limit else "  GPU limit  at its default"
    )
    typer.echo(f"  usable     {machine.usable_bytes / 1e9:.0f}GB")
    typer.echo("")
    typer.echo("  A model of about this size fits, leaving room for context:")
    typer.echo("")
    for bits, parameters in sizes_that_fit(machine):
        typer.echo(f"    {bits:>2}-bit   {parameters / BILLION:>5.0f}B parameters")
    typer.echo("")
    typer.echo(
        f"  Load one in your runtime, then `offgrid run`. Profile: {DEFAULT_PATH}"
    )

    if limit is None:
        typer.echo("")
        typer.echo("  More fits with the GPU limit raised, which a reboot undoes:")
        wanted = int(machine.memory_bytes * 0.875 / (1024 * 1024))
        typer.echo(f"    sudo sysctl iogpu.wired_limit_mb={wanted}")


@app.command()
def doctor() -> None:
    """Check that the runtime is reachable and holding a model."""
    profile = _profile()
    model = _resident(profile)

    typer.echo(f"  runtime   {profile.host} reachable")
    typer.echo(f"  model     {model.identifier}")
    typer.echo(f"  context   {model.context_limit or 'unstated'}")
    typer.echo(f"  agent     {profile.agent}, speaking {agent_dialect().value}")


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

    # Both of these are knowable before a load, and a load is a minute of
    # someone's time.
    with _reported():
        require_compatible(runtime_dialect(), agent_dialect())
    prepare(CONFIG_DIR)

    wanted = model_name or profile.model
    model = _chosen(profile, wanted) if wanted else _resident(profile)

    typer.echo(
        f"  {model.identifier}, context {model.context_limit or 'unstated'}", err=True
    )

    launch = plan(
        model,
        host=profile.host,
        config_dir=CONFIG_DIR,
        token=TOKEN,
        passthrough=list(context.args),
    )

    try:
        code = start(launch)
    except KeyboardInterrupt:
        code = 130
    except OSError as error:
        typer.echo(
            f"  Could not start {launch.argv[0]}: {error}. "
            "Install it, or put it on PATH."
        )
        code = 127
    finally:
        _let_go(profile.host, model.identifier)

    raise typer.Exit(code)


def start(launch: Launch) -> int:
    """Run the agent and wait for it.

    offgrid stays alive as its parent rather than handing over the process,
    because a model held in memory has to be let go by somebody once the
    agent is done with it. Being asked to stop is passed on for the same
    reason: an agent left running would be talking to a model offgrid is
    about to let go of.

    :param launch: The environment and command to run.

    :return: The agent's exit code, or what a shell reports for the signal
        that killed it.

    :raise OSError: When the agent cannot be started at all.
    """
    agent = subprocess.Popen(launch.argv, env={**os.environ, **launch.env})

    def pass_on(number: int, frame: object) -> None:
        """Stop the agent, so offgrid outlives it and can let the model go."""
        agent.terminate()

    replaced = [(number, signal.signal(number, pass_on)) for number in STOPS]

    try:
        code = agent.wait()
    finally:
        for number, handler in replaced:
            signal.signal(number, handler)

    return code if code >= 0 else 128 - code


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
        typer.echo(f"  {error}")
        raise typer.Exit(1) from error


def _profile() -> Profile:
    """Read the stored profile, or explain how to make one.

    :return: The stored profile.
    """
    with _reported():
        return load_profile(DEFAULT_PATH)


def _chosen(profile: Profile, identifier: str) -> Model:
    """Hold the named model in memory, whatever the runtime is holding now.

    :param profile: Where to reach the runtime.
    :param identifier: The model asked for.

    :return: The model that will answer.
    """
    payload = _catalogue(profile)
    known = {model.identifier: model for model in parse_models(payload)}
    if identifier not in known:
        typer.echo(
            f"  The runtime at {profile.host} does not have {identifier}. "
            "`offgrid doctor` lists what it holds."
        )
        raise typer.Exit(1)

    held = resident(payload)
    if held is not None and held.identifier == identifier:
        return held

    _clear(profile.host, payload, identifier)

    typer.echo(f"  Loading {identifier} ...", nl=False)
    started = time.monotonic()
    with _reported():
        try:
            load_model(profile.host, identifier)
        except OffgridError:
            typer.echo("")
            raise
    typer.echo(f" ready in {time.monotonic() - started:.0f}s")

    return _now_holding(profile, identifier)


def _now_holding(profile: Profile, identifier: str) -> Model:
    """Read back a model from the runtime that has just loaded it.

    A catalogue entry states a model's ceiling until it is loaded, and the
    window it is served at once it is. Sizing the agent's context from the
    ceiling means never compacting, and the runtime truncates the prefix
    instead — which is the failure compacting exists to avoid.

    :param profile: Where to reach the runtime.
    :param identifier: The model that was loaded.

    :return: The model as the runtime now serves it.
    """
    held = {model.identifier: model for model in loaded(_catalogue(profile))}

    if identifier not in held:
        typer.echo(
            f"  The runtime at {profile.host} accepted {identifier} but is not "
            "holding it. Load it in the runtime directly to see what it says."
        )
        raise typer.Exit(1)

    return held[identifier]


def _clear(host: str, payload: dict, wanted: str) -> None:
    """Let go of every model held that is not the one being asked for.

    One machine, one pool of memory: a model left loaded is memory the rest
    of the machine cannot use.

    :param host: Address the runtime listens on.
    :param payload: The runtime's catalogue.
    :param wanted: The model that will answer.
    """
    held = resident(payload)
    if held is None or held.identifier == wanted:
        return

    typer.echo(f"  Letting go of {held.identifier}, whose cached prefix goes with it.")
    _let_go(host, held.identifier)


def _let_go(host: str, identifier: str) -> None:
    """Unload a model, saying so if the runtime will not.

    :param host: Address the runtime listens on.
    :param identifier: The model to unload.
    """
    try:
        unload(host, identifier)
    except OffgridError as error:
        typer.echo(f"  The runtime is still holding {identifier}: {error}")


def _catalogue(profile: Profile) -> dict:
    """Fetch the runtime's catalogue, or explain why it could not be reached.

    :param profile: Where to reach the runtime.

    :return: The decoded catalogue.
    """
    with _reported():
        return catalogue(profile.host)


def _resident(profile: Profile) -> Model:
    """Find the model the runtime is holding, or explain that it holds none.

    :param profile: Where to reach the runtime.

    :return: The model that would answer.
    """
    held = resident(_catalogue(profile))

    if held is None:
        typer.echo(
            f"  The runtime at {profile.host} is holding no model. "
            "Load a model in it, then try again."
        )
        raise typer.Exit(1)

    return held


def main() -> None:
    """Run the command line, reporting offgrid's own errors as messages.

    A command reports what it can itself. This is the net under everything
    else, so an error offgrid raised on purpose reaches the terminal as the
    sentence it was written as rather than as a traceback.
    """
    try:
        app()
    except OffgridError as error:
        typer.echo(f"  {error}")
        sys.exit(1)
