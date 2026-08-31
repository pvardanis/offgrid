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
from offgrid.domain.assembling import (
    AgentOnThisMachine,
    WhatCouldBeRun,
    WouldNotAnswer,
)
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
from offgrid.domain.running.agent import (
    Agent,
    AgentName,
    Passthrough,
)
from offgrid.domain.running.agent_presence import find_agent_on_path
from offgrid.domain.running.answering import (
    find_resident_model,
    name_what_would_answer,
)
from offgrid.domain.running.discarded_windows import DiscardedWindow
from offgrid.domain.running.model import Model
from offgrid.domain.running.runtime import Runtime, RuntimeName
from offgrid.runtimes import connect_runtime, create_runtime_config
from offgrid.shared.exceptions import (
    AgentSettingsError,
    DiscardedWindowsUnreadableError,
)


def there_is_no_profile(path: Path) -> bool:
    """Say whether a fresh machine has no profile to read.

    Absence is a stranger who has not run `setup`. A symlink is somebody having
    claimed the path, so it counts as a profile whether or not the far end is
    there: deciding on what resolves would read a link to a file that has moved
    as a machine that was never set up, and answer about a runtime nobody chose.
    Written once because three surfaces ask it — the screen's report, the
    command line's choice whether to measure, and `recommend` — and the symlink
    subtlety is a rule to keep in one place. `setup` is not one: it does its own
    existence check while writing a fresh profile, and refuses nothing.

    :param path: Where the profile would be kept.

    :return: Whether there is no profile there to read.
    """
    return not path.exists() and not path.is_symlink()


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
    return bind_profile(read_profile(profile_path), passthrough)


def bind_profile(
    profile: Profile, passthrough: Passthrough = ()
) -> tuple[Profile, Runtime, Agent]:
    """Bind both adapters a profile already in memory names.

    What the picker hands back is a profile assembled in memory rather than one
    read from a file, so a run reached from the screen binds this rather than
    reading the profile again — and binds exactly what was on screen.

    :param profile: What a run is made from.
    :param passthrough: Arguments handed to the agent unchanged.

    :return: The profile, the runtime, and the agent.
    """
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

    :raise OffgridError: When the profile is not one, when nothing answered
        for the runtime it names, or when the agent's own settings are there
        and cannot be read. That last one stops the whole report where the
        record below is only a line of it, and the difference is which of
        them a run reads before it starts.
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


def read_what_could_be_run(profile_path: Path) -> WhatCouldBeRun:
    """Ask the machine everything a person could pick from, once.

    Once, because what the picker does afterwards is arithmetic: it recomputes
    a report as a highlight moves, and a surface that fetched a catalogue per
    keystroke would make looking around cost what committing costs.

    Every agent offgrid drives is asked, not only the one the profile names,
    since the list is what offgrid supports rather than what this machine has.
    One that will not answer is carried as a row that says so: a screen that
    refused to open over an agent nobody picked would report the machine as
    unreadable when one file on it is.

    :param profile_path: Where to read the profile from.

    :return: The profile, what the runtime holds and has, and what each agent
        said about itself here.

    :raise OffgridError: When there is a profile and it is not one, or when
        nothing answered for the runtime named. Both stop the picker having
        anything to show. A missing profile is not one of them: a stranger
        following the README has written none, and the screen measures for them
        rather than refusing.
    """
    profile = _read_profile_or_default(profile_path)
    runtime = connect_runtime(profile.runtime)

    downloaded_models = tuple(runtime.read_catalogue())

    # Asked once and read twice, because what is held and which of it answers
    # are two questions about one moment: asked separately, a model can be let
    # go of in between and the two would describe different machines.
    in_memory = runtime.read_held()
    resident = name_what_would_answer(in_memory)

    discarded, unreadable = _read_what_was_discarded(profile, resident)

    return WhatCouldBeRun(
        profile=profile,
        runtime=WhatTheRuntimeAnswered(
            resident=resident,
            served=runtime.dialects,
            discarded=discarded,
            unreadable=unreadable,
        ),
        downloaded_models=downloaded_models,
        held=frozenset(model.identifier for model in in_memory),
        agents=tuple(_ask_every_agent(profile)),
    )


def _read_profile_or_default(profile_path: Path) -> Profile:
    """Read the profile, or default it where a fresh machine has none.

    Where `there_is_no_profile`, the screen sizes the machine for a stranger
    rather than refusing: it assembles onto what `setup` would have written. A
    file that is there and will not load is refused as everywhere else — it
    names a runtime, and guessing past it would answer about an adapter its
    owner did not choose.

    :param profile_path: Where the profile is kept.

    :return: What was written down, or the default where nothing was.

    :raise ProfileError: When a profile is there and is not one.
    """
    if there_is_no_profile(profile_path):
        # Deferred so setup, which imports this module for `read_profile`, is
        # not imported back at module load: the default is asked for at the one
        # moment a fresh machine opens the screen.
        from offgrid.cli.setup import default_profile

        return default_profile()

    return read_profile(profile_path)


def _ask_every_agent(profile: Profile) -> list[AgentOnThisMachine]:
    """Ask each agent offgrid drives what it states about itself here.

    :param profile: What was written down.

    :return: One reading per agent, in the order the names are declared.
    """
    return [_ask_an_agent(profile, name) for name in AgentName]


def _ask_an_agent(profile: Profile, name: AgentName) -> AgentOnThisMachine:
    """Bind one agent and read what it says, or why it would not say it.

    The config is built in here rather than handed in, so that it is inside the
    guard: an adapter whose defaults will not build is one agent that cannot
    answer, and outside it would be a screen that will not open over an agent
    nobody picked.

    Only `AgentSettingsError` is caught, because that is what this is about —
    an agent's own settings file being there and unreadable. Anything else the
    reading grows later is a different fault with a different remedy, and would
    be reported as "did not answer" beside a greyed-out row: a runtime that is
    down, or a finding that something can reach off this machine, are both
    worse than useless said that way.

    :param profile: What was written down.
    :param name: The agent to ask.

    :return: What it answered, or the sentence explaining what stopped it.
    """
    try:
        # The profile's own section for the agent it names, so that an agent a
        # person has settings for is reported with them rather than with
        # defaults; what every agent needs for the rest.
        config = (
            profile.agent
            if name is profile.agent_name
            else create_agent_config(
                {"name": name.value}, runtime_host=profile.runtime_host
            )
        )

        agent = prepare_agent(config)
        terms = agent.terms

        answered = WhatTheAgentAnswered(
            terms=terms,
            found_at=find_agent_on_path(terms.command),
            could_leave=agent.read_what_leaves_this_machine(),
            kept=agent.conversations,
        )
    except AgentSettingsError as error:
        return AgentOnThisMachine(
            config=create_agent_config(
                {"name": name.value}, runtime_host=profile.runtime_host
            ),
            answered=WouldNotAnswer(str(error)),
        )

    return AgentOnThisMachine(config=config, answered=answered)


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
            profile.runtime_name, profile.runtime_host, discarded_windows.DEFAULT_PATH
        )
    except DiscardedWindowsUnreadableError as error:
        return (), str(error)

    return tuple(r for r in records if r.identifier == resident.identifier), None
