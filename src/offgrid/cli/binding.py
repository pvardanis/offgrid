"""Turning what a profile names into the runtime and agent a run talks to.

A section of the file is a name and whatever that adapter reads; it becomes a
config only once something knows which adapters there are. That is what this
module has and the domain may not: both registries, asked in the one order a
run needs them, since an agent is built from an address the runtime's section
holds.
"""

from pathlib import Path

from offgrid.agents import create_agent_config, prepare_agent
from offgrid.domain.profile import (
    Profile,
    create_profile,
    load_yaml,
    refuse_profile_section,
)
from offgrid.domain.running.agent import Agent, AgentName, Passthrough
from offgrid.domain.running.runtime import Runtime, RuntimeName
from offgrid.runtimes import connect_runtime, create_runtime_config


def read_profile(path: Path) -> Profile:
    """Read a profile, asking each registry to read the section that is its own.

    :param path: Where to read it from.

    :return: What a run is made from.

    :raise ProfileError: When the file is not one, or a section is not one its
        adapter can read.
    """
    body = load_yaml(path)
    said = {port: body.get(port, {}) for port in ("runtime", "agent")}

    with refuse_profile_section(said["runtime"], port="runtime", names=RuntimeName):
        runtime = create_runtime_config(said["runtime"])

    with refuse_profile_section(said["agent"], port="agent", names=AgentName):
        agent = create_agent_config(said["agent"], runtime_host=runtime.host)

    return create_profile(body, runtime=runtime, agent=agent)


def bind_run(
    profile_path: Path, passthrough: Passthrough = ()
) -> tuple[Profile, Runtime, Agent]:
    """Read the profile, and bind both adapters it names.

    What every command that talks to the runtime starts with. A command with
    no arguments of its own — `doctor` — binds an agent that reports on its
    configuration alone.

    Where the profile is kept is passed rather than read here, so that this
    answers about the file it was given rather than about whichever one the
    module happened to name when it was imported.

    :param profile_path: Where to read the profile from.
    :param passthrough: Arguments handed to the agent unchanged.

    :return: What was stored, the runtime, and the agent.

    :raise ProfileError: When the profile is not one, or a section is not one
        its adapter can read.
    """
    profile = read_profile(profile_path)

    runtime = connect_runtime(profile.runtime)
    agent = prepare_agent(profile.agent, passthrough)

    return profile, runtime, agent
