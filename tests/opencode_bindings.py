"""OpenCode bound the way the command line binds it, for the tests about it.

Several files ask about this adapter — what a run derives for one launch, what
offgrid writes into the directory it keeps, and what a command says about it —
and they start from the same binding and read the same two places back.
"""

import json
from pathlib import Path

from typer.testing import CliRunner

from offgrid.agents import create_agent_config
from offgrid.agents.opencode import prepare
from offgrid.agents.opencode.launching import CONFIG_CONTENT
from offgrid.cli import app
from offgrid.domain.running.agent import Agent, Passthrough
from offgrid.domain.running.launch import Launch
from offgrid.domain.running.model import Model
from tests.profiles import add_to_section

HOST = "127.0.0.1:1234"
WANTED = "qwen/qwen3.6-35b-a3b"
SETTINGS = "opencode.json"
STORE = "store"
NAMED = "opencode"


def name_opencode(here: Path) -> None:
    """Write a profile, then switch the agent the way a person would.

    `setup` writes the Claude Code adapter and is deliberately not taught to
    choose, so naming OpenCode is the one-line hand-edit it takes to switch.

    :param here: Where the profile is.
    """
    CliRunner().invoke(app, ["setup"])

    add_to_section(here, "agent", name=NAMED)


def write_configuration(here: Path, body: str) -> None:
    """Leave a configuration in the directory OpenCode is run out of.

    The directory as well as the file, because a hand-edited configuration is
    a thing a person can leave on a machine that has never run the agent.

    :param here: Where offgrid keeps what it writes.
    :param body: What the file holds.
    """
    config = here / NAMED
    config.mkdir(exist_ok=True)

    (config / SETTINGS).write_text(body)


# Every spelling of a runtime's name a value might carry, because the claim is
# that this adapter knows runtimes have no names at all — and a check for the
# profile's spelling alone passes a provider labelled the way a person reads it.
RUNTIME_SPELLINGS = ("lmstudio", "lm studio", "lm-studio")


def bind(host: str = HOST, passthrough: Passthrough = (), **said) -> Agent:
    """Bind the adapter the way the registry does, from what a profile said.

    :param host: Where the runtime listens.
    :param passthrough: Arguments handed to the agent unchanged.
    :param said: Whatever else the profile's agent section says.

    :return: The adapter under test.
    """
    return prepare(
        create_agent_config({"name": "opencode"} | said, runtime_host=host), passthrough
    )


def plan_for(agent: Agent, window: int | None = 32768) -> Launch:
    """Ask the agent how it would start against the model that will answer.

    :param agent: The adapter under test.
    :param window: What the runtime settled on, or ``None`` where it states
        nothing.

    :return: The environment and command it answered with.
    """
    return agent.plan(
        Model(identifier=WANTED, context_ceiling=262144, context_window=window)
    )


def read_derived(launch: Launch) -> dict:
    """Read what the run settled, as OpenCode reads it from the environment.

    :param launch: What the agent answered with.

    :return: The configuration it carries.
    """
    return json.loads(launch.env[CONFIG_CONTENT])


def read_everything_carried(launch: Launch) -> str:
    """Say everything a launch carries, to look in it for a value left over.

    :param launch: What the agent answered with.

    :return: Its environment and its arguments, as one string.
    """
    return " ".join([*launch.env.values(), *launch.argv])


def read_written(config_dir: Path) -> dict:
    """Read what `configure` left in the file OpenCode is pointed at.

    :param config_dir: Where the agent keeps its own file.

    :return: What the file holds.
    """
    return json.loads((config_dir / SETTINGS).read_text())
