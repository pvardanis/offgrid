"""Measure this machine, and record how to reach the runtime."""

import typer

from offgrid.agents import create_agent_config
from offgrid.cli.binding import read_profile
from offgrid.cli.reporting import reporting
from offgrid.domain.profile import DEFAULT_PATH, Profile, save_profile
from offgrid.domain.running.agent import AgentConfig, AgentName
from offgrid.domain.running.runtime import RuntimeConfig, RuntimeName
from offgrid.domain.sizing.machine import detect, suggest_raising_the_gpu_limit
from offgrid.domain.sizing.measuring import describe_the_machine
from offgrid.runtimes import create_runtime_config
from offgrid.shared.exceptions import ProfileError
from offgrid.shared.say import tell

DEFAULT_HOST = "127.0.0.1:1234"
# What a fresh profile names. Which adapter to write down is this command's
# decision, not something the file may leave out and have guessed for it.
DEFAULT_RUNTIME = RuntimeName.LMSTUDIO
DEFAULT_AGENT = AgentName.CLAUDE_CODE


def default_profile() -> Profile:
    """Build the profile a fresh machine gets, without reading a file.

    What `setup` would write where there is none: the runtime and agent offgrid
    defaults to, listening where it defaults to, and no model named. The screen
    assembles onto this when a stranger opens it before running `setup`, so that
    nobody is sent away to another command before seeing anything.

    :return: The default profile.
    """
    return Profile(
        runtime=create_runtime_config(
            {"name": DEFAULT_RUNTIME.value, "host": DEFAULT_HOST}
        ),
        agent=create_agent_config(
            {"name": DEFAULT_AGENT.value}, runtime_host=DEFAULT_HOST
        ),
    )


def setup(
    host: str = typer.Option(None, help="Where the runtime listens."),
) -> None:
    """Measure this machine and record how to reach the runtime."""
    machine = detect()
    stored = _get_stored_profile()
    listening_at = host or (stored.runtime_host if stored else DEFAULT_HOST)

    runtime_config, agent_config = _get_runtime_and_agent_configs(
        stored, listening_at=listening_at
    )

    # Written even where it says nothing, so both keys are there to edit.
    kept = {"model": stored.model} if stored else {}

    save_profile(
        Profile(runtime=runtime_config, agent=agent_config, **kept), DEFAULT_PATH
    )

    for line in describe_the_machine(machine):
        tell(line)
    tell(f"Load one in your runtime, then `offgrid run`. Profile: {DEFAULT_PATH}")

    advice = suggest_raising_the_gpu_limit(machine)
    if advice:
        tell("")
        for line in advice:
            tell(line)


# What was stored is carried over whole rather than rebuilt from the defaults,
# so a re-run keeps the adapters named and whatever settings of their own they
# were given. Only the address moves, and it moves in both places at once.
@reporting()
def _get_runtime_and_agent_configs(
    stored: Profile | None, *, listening_at: str
) -> tuple[RuntimeConfig, AgentConfig]:
    """Settle which runtime and which agent the profile will name.

    :param stored: The profile already there, or ``None`` where there is none.
    :param listening_at: Where the runtime listens.

    :return: The runtime's config and the agent's.
    """
    runtime_config = (
        stored.runtime.model_copy(update={"host": listening_at})
        if stored
        else create_runtime_config(
            {"name": DEFAULT_RUNTIME.value, "host": listening_at}
        )
    )
    agent_config = (
        stored.agent.model_copy(update={"runtime_host": listening_at})
        if stored
        else create_agent_config(
            {"name": DEFAULT_AGENT.value}, runtime_host=listening_at
        )
    )

    return runtime_config, agent_config


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
