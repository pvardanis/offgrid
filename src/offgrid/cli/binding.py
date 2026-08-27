"""Turning what a profile names into the runtime and agent a run talks to.

A section of the file is a name and whatever that adapter reads; it becomes a
config only once something knows which adapters there are. That is what this
module has and the domain may not: both registries, asked in the one order a
run needs them, since an agent is built from an address the runtime's section
holds.

Asking each of them what it says is here too, because it is the same
composition one step further on, and because both surfaces that show the
answer start from it.
"""

from pathlib import Path

from offgrid.agents import create_agent_config, prepare_agent
from offgrid.domain.checkup import (
    Checkup,
    WhatTheAgentAnswered,
    WhatTheRuntimeAnswered,
)
from offgrid.domain.profile import (
    Profile,
    create_profile,
    load_yaml,
    refuse_profile_section,
)
from offgrid.domain.running import discarded_windows
from offgrid.domain.running.agent import Agent, AgentName, Passthrough
from offgrid.domain.running.agent_presence import find_agent_on_path
from offgrid.domain.running.answering import find_resident_model
from offgrid.domain.running.discarded_windows import DiscardedWindow
from offgrid.domain.running.model import Model
from offgrid.domain.running.runtime import Runtime, RuntimeName
from offgrid.runtimes import connect_runtime, create_runtime_config
from offgrid.shared.exceptions import DiscardedWindowsUnreadableError


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


def read_what_can_be_read(profile_path: Path) -> Checkup:
    """Ask the profile, the runtime and the agent what each of them says.

    Everything is read before anything is said, so that a fault in any of it
    is reported as offgrid's own error rather than as a traceback under lines
    that already looked like an answer. What a surface does about such a
    fault is its own: a command stops on it, a screen shows it and stays open.

    :param profile_path: Where to read the profile from.

    :return: What each of them answered.

    :raise OffgridError: When the profile is not one, or nothing answered for
        the runtime it names.
    """
    profile, runtime, agent = bind_run(profile_path)

    resident = find_resident_model(runtime)
    discarded, unreadable = _read_what_was_discarded(profile, resident)

    agent_terms = agent.terms

    return Checkup(
        profile=profile,
        runtime=WhatTheRuntimeAnswered(
            resident=resident,
            served=runtime.dialects,
            discarded=discarded,
            unreadable=unreadable,
        ),
        agent=WhatTheAgentAnswered(
            terms=agent_terms,
            found_at=find_agent_on_path(agent_terms.command),
            could_leave=agent.read_what_leaves_this_machine(),
            kept=agent.conversations,
        ),
    )


def _read_what_was_discarded(
    profile: Profile, resident: Model | None
) -> tuple[tuple[DiscardedWindow, ...], str | None]:
    """Read the windows this runtime discarded for the model it is holding.

    A file that will not read is a finding rather than a fault here. Every
    other reading in the report succeeded, and refusing to say any of them
    over a record offgrid keeps for itself would answer a person who ran
    `doctor` because something is wrong with one line about a file they have
    never heard of.

    :param profile: What was written down.
    :param resident: The model the runtime is holding, or ``None`` for none.

    :return: Every window it discarded for that model, and why the records
        could not be read where they could not.
    """
    if resident is None:
        return (), None

    try:
        records = discarded_windows.read_discarded_windows(
            profile.runtime.name, profile.runtime.host, discarded_windows.DEFAULT_PATH
        )
    except DiscardedWindowsUnreadableError as error:
        return (), str(error)

    return tuple(r for r in records if r.identifier == resident.identifier), None
