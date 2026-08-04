"""The three things offgrid does: describe, check, and launch."""

import os
import sys
import time
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
from offgrid.runtimes.lmstudio import catalogue, parse_models, resident
from offgrid.runtimes.lmstudio import dialect as runtime_dialect
from offgrid.runtimes.lmstudio import load as load_model

CONFIG_DIR = Path.home() / ".offgrid" / "claude-code"
DEFAULT_HOST = "127.0.0.1:1234"
# The local server ignores it; the agent refuses to start without one.
TOKEN = "local"
BILLION = 1e9
GIB = 1024**3

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
    model = _chosen(profile, model_name) if model_name else _resident(profile)
    require_compatible(runtime_dialect(), agent_dialect())

    prepare(CONFIG_DIR)
    typer.echo(
        f"  {model.identifier}, context {model.context_limit or 'unstated'}", err=True
    )
    start(
        plan(
            model,
            host=profile.host,
            config_dir=CONFIG_DIR,
            token=TOKEN,
            passthrough=list(context.args),
        )
    )


def start(launch: Launch) -> None:
    """Replace this process with the agent.

    :param launch: The environment and command to run.
    """
    os.execvpe(launch.argv[0], launch.argv, {**os.environ, **launch.env})


def _profile() -> Profile:
    """Read the stored profile, or explain how to make one.

    :return: The stored profile.
    """
    try:
        return load_profile(DEFAULT_PATH)
    except OffgridError as error:
        typer.echo(f"  {error}")
        raise typer.Exit(1) from error


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

    if held is not None:
        typer.echo(f"  Swapping from {held.identifier}, whose cached prefix is lost.")

    typer.echo(f"  Loading {identifier} ...", nl=False)
    started = time.monotonic()
    try:
        load_model(profile.host, identifier)
    except OffgridError as error:
        typer.echo("")
        typer.echo(f"  {error}")
        raise typer.Exit(1) from error
    typer.echo(f" ready in {time.monotonic() - started:.0f}s")

    return known[identifier]


def _catalogue(profile: Profile) -> dict:
    """Fetch the runtime's catalogue, or explain why it could not be reached.

    :param profile: Where to reach the runtime.

    :return: The decoded catalogue.
    """
    try:
        return catalogue(profile.host)
    except OffgridError as error:
        typer.echo(f"  {error}")
        raise typer.Exit(1) from error


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
    """Run the command line."""
    sys.exit(app())
