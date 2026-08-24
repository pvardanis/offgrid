"""OpenCode bound the way the command line binds it, for the tests about it.

Two files ask about this adapter — what a run derives for one launch, and what
offgrid writes into the directory it keeps — and both start from the same
binding and read the same two places back.
"""

import json
from pathlib import Path

from offgrid.agents import create_agent_config
from offgrid.agents.opencode import prepare
from offgrid.agents.opencode.launching import CONFIG_CONTENT
from offgrid.domain.running.agent import Agent, Passthrough
from offgrid.domain.running.launch import Launch
from offgrid.domain.running.model import Model

HOST = "127.0.0.1:1234"
WANTED = "qwen/qwen3.6-35b-a3b"
SETTINGS = "opencode.json"

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
