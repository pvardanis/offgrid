"""Measure this machine, and record how to reach the runtime."""

import typer

from offgrid.agents import create_agent_config
from offgrid.binding import read_profile
from offgrid.cli.reporting import reporting
from offgrid.domain.profile import DEFAULT_PATH, Profile, save_profile
from offgrid.domain.running.agent import AgentName
from offgrid.domain.running.runtime import RuntimeName
from offgrid.domain.sizing.fit import BYTES_PER_GB, get_sizes_that_fit
from offgrid.domain.sizing.machine import detect, suggest_raising_the_gpu_limit
from offgrid.runtimes import create_runtime_config
from offgrid.shared.exceptions import ProfileError
from offgrid.shared.say import tell

DEFAULT_HOST = "127.0.0.1:1234"
# What a fresh profile names. Which adapter to write down is this command's
# decision, not something the file may leave out and have guessed for it.
DEFAULT_RUNTIME = RuntimeName.LMSTUDIO
DEFAULT_AGENT = AgentName.CLAUDE_CODE
BILLION = 1e9
GIB = 1024**3


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
    with reporting():
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

    # Written even where it says nothing, so both keys are there to edit.
    kept = {"model": stored.model} if stored else {}

    save_profile(Profile(runtime=runtime, agent=agent, **kept), DEFAULT_PATH)

    tell(f"{machine.chip} · {machine.memory_bytes / GIB:.0f}GB unified memory")
    limit = machine.wired_limit_bytes
    tell(f"GPU limit  {limit / GIB:.0f}GB" if limit else "GPU limit  at its default")
    tell(f"usable     {machine.usable_bytes / BYTES_PER_GB:.0f}GB")
    tell("")
    tell("A model of about this size fits, leaving room for context:")
    tell("")
    for bits, parameters in get_sizes_that_fit(machine):
        tell(f"  {bits:>2}-bit   {parameters / BILLION:>5.0f}B parameters")
    tell("")
    tell("`offgrid recommend` names the published models that fit.")
    tell(f"Load one in your runtime, then `offgrid run`. Profile: {DEFAULT_PATH}")

    advice = suggest_raising_the_gpu_limit(machine)
    if advice:
        tell("")
        for line in advice:
            tell(line)


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

        tell(f"{error}")
        tell(f"What was there is at {kept}. Writing a fresh profile.")
        return None
