"""What could be run on this machine, and what running one pairing would cost.

Everything is read once, and every report after that is composed out of what
came back. Moving a highlight reaches no runtime, opens no file and writes
nothing, which is what makes looking around free.

The report itself is `doctor`'s, recomputed against the pairing rather than
against the file — the same lines from the same place, so that two surfaces
cannot word one fact differently — with what running it would cost said under
them. That last part is the picker's own: `doctor` reports the model the
runtime is already holding, so it has never had a load to price.

A pairing names an agent and a model and not a runtime, because there is one
runtime adapter and its config is the profile's. The list shows it, so that a
person can see what offgrid drives; the day there are two, this is where the
second one lands.
"""

from dataclasses import dataclass, replace

from offgrid.domain.checkup import (
    Checkup,
    WhatTheAgentAnswered,
    WhatTheRuntimeAnswered,
    describe_what_was_read,
)
from offgrid.domain.profile import Profile
from offgrid.domain.running.agent import AgentConfig, AgentName
from offgrid.domain.running.dialect import require_compatible
from offgrid.domain.running.model import Model, ModelRequest
from offgrid.shared.exceptions import DialectMismatchError
from offgrid.shared.wording import (
    REMEDY,
    describe_what_was_stated,
    say_in_columns,
    say_indented,
)

RUNNING = "running"
"""What the lines about the cost of a pairing are labelled.

Its own heading rather than more lines under `model`, because it is the one
part of the report that is about a keystroke nobody has pressed yet.
"""

AGENT_COLUMN = 14
"""How wide an agent's name is on its row, so that what is said about it lines
up down the list. Wide enough for the longest name offgrid drives, plus a gap.
"""

MODEL_COLUMN = 26
"""How wide a model's identifier is on its row.

An identifier is a publisher and a name, and a long one overflows rather than
being cut: a truncated identifier is not the model, and a person reading the
list has to be able to tell two builds of one model apart.
"""

HELD_COLUMN = 6
"""How wide the column saying a model is in memory is, blank where it is not."""


@dataclass(frozen=True)
class AgentOnThisMachine:
    """One agent offgrid has an adapter for, and what it answered here.

    Every agent offgrid drives is here whether or not the machine has it, so
    that the list is what offgrid supports rather than what happens to be
    installed. What is absent is marked rather than left out.

    :param name: The agent, as a profile names it.
    :param config: What its section of a profile would hold, which is the
        profile's own where the profile names this agent.
    :param answered: What it said about itself, and ``None`` where asking it
        failed.
    :param unreadable: Why asking it failed, where it did. An agent whose own
        settings will not read is a row a person can see and not pick, rather
        than a screen that will not open.
    """

    name: AgentName
    config: AgentConfig
    answered: WhatTheAgentAnswered | None
    unreadable: str | None

    @property
    def is_on_this_machine(self) -> bool:
        """Whether a run could start this agent as things stand.

        :return: Whether it answered, and whether the `PATH` has its command.
        """
        return self.answered is not None and self.answered.found_at is not None


@dataclass(frozen=True)
class WhatCouldBeRun:
    """Everything a person picks from, read before any of it is shown.

    :param profile: What is written down, which is what the picker starts
        assembled as.
    :param runtime: What the runtime answered, the model it is holding
        included.
    :param downloaded: Every model the runtime has, held or not, held first.
    :param held: Which of them are in memory, so that a pairing can be priced
        without asking again.
    :param agents: Every agent offgrid drives, and what each said here.
    """

    profile: Profile
    runtime: WhatTheRuntimeAnswered
    downloaded: tuple[Model, ...]
    held: frozenset[str]
    agents: tuple[AgentOnThisMachine, ...]


@dataclass(frozen=True)
class Assembly:
    """The agent and model a highlight is sitting on.

    :param agent: The agent that would be started.
    :param model: The model that would answer, or ``None`` where the pairing
        asks for nothing and takes whatever the runtime is holding — which is
        what a profile naming no model says, and what the picker opens on.
    """

    agent: AgentName
    model: str | None


def order_models_held_first(what: WhatCouldBeRun) -> tuple[Model, ...]:
    """Put the models that cost nothing to start at the top of the list.

    Held first and each group in the order the runtime answered in, so that
    two readings of an unchanged machine list them alike.

    :param what: Everything that was read.

    :return: Every model downloaded, the held ones first.
    """
    return tuple(
        sorted(what.downloaded, key=lambda model: model.identifier not in what.held)
    )


def open_on_what_the_profile_holds(what: WhatCouldBeRun) -> Assembly:
    """Say what the picker is assembled as before anybody presses a key.

    The file itself, so that the first thing shown is what a run would do
    today. A profile naming no model keeps naming none: the highlight lands on
    the model that would answer, and sitting on a row is not the same statement
    as having written its name down.

    :param what: Everything that was read.

    :return: The pairing the file holds.
    """
    return Assembly(agent=what.profile.agent.name, model=what.profile.model.identifier)


def find_what_would_answer(what: WhatCouldBeRun, assembly: Assembly) -> str | None:
    """Name the model a pairing would run against, which may be none.

    A pairing naming no model takes whatever the runtime is holding, so the row
    to sit on is the resident one. Where nothing is held either, there is no
    row to sit on.

    :param what: Everything that was read.
    :param assembly: What the highlight is on.

    :return: The model's identifier, or ``None`` where none would answer.
    """
    if assembly.model is not None:
        return assembly.model

    resident = what.runtime.resident

    return resident.identifier if resident is not None else None


def read_the_highlight(
    what: WhatCouldBeRun, *, agent: str | None, model: str | None
) -> Assembly:
    """Read what the highlights are sitting on as a pairing.

    A list with no reachable row at all falls back on what the profile names,
    so that a machine with neither agent installed still reports on the one a
    run would try to start.

    Sitting on the model the runtime is already holding is read as the profile's
    own statement about a model rather than as naming that one — which, for a
    profile that names none, is naming none. The two describe the same run
    today, and the difference is only what a save would write down; a person who
    has moved the highlight nowhere has asked for nothing.

    :param what: Everything that was read.
    :param agent: What the agent list's highlight is on, or ``None`` for none.
    :param model: What the model list's highlight is on, or ``None`` for none.

    :return: The pairing to report on.
    """
    if agent is None:
        return open_on_what_the_profile_holds(what)

    resident = what.runtime.resident
    sitting_on_the_resident = resident is not None and model == resident.identifier

    return Assembly(
        agent=AgentName(agent),
        model=what.profile.model.identifier if sitting_on_the_resident else model,
    )


def describe_an_agent_row(agent: AgentOnThisMachine) -> str:
    """Lay out the row one agent is listed as.

    An agent this machine has not got is marked on the row rather than left
    out, because the list is also how a person learns what offgrid supports.
    Where to get it is the report's business, which has the width for a link.

    :param agent: The agent to lay out.

    :return: The row, as it is read.
    """
    if agent.unreadable is not None:
        return f"{agent.name.value:<{AGENT_COLUMN}}did not answer"

    if not agent.is_on_this_machine:
        return f"{agent.name.value:<{AGENT_COLUMN}}not installed"

    return agent.name.value


def describe_a_model_row(model: Model, *, held: bool) -> str:
    """Lay out the row one model is listed as.

    Padded text rather than real columns, which is what `OptionList` costs and
    what skipping a row the cursor may not reach buys.

    :param model: The model to lay out.
    :param held: Whether the runtime has it in memory.

    :return: The row, as it is read.
    """
    return (
        f"{model.identifier:<{MODEL_COLUMN}}"
        f"{'held' if held else '':<{HELD_COLUMN}}"
        f"{describe_what_was_stated(model.context_ceiling)}"
    )


def describe_what_would_run(
    what: WhatCouldBeRun, assembly: Assembly
) -> tuple[str, ...]:
    """Put what running a pairing would do into the lines it is read as.

    :param what: Everything that was read.
    :param assembly: What the highlight is on.

    :return: The lines to say, in the order they are read.
    """
    agent = find_agent(what, assembly.agent)

    if agent.answered is None:
        return _describe_an_agent_that_would_not_answer(agent)

    checkup = Checkup(
        profile=_as_assembled(what.profile, agent, assembly),
        runtime=replace(what.runtime, resident=_what_would_answer(what, assembly)),
        agent=agent.answered,
    )

    return (
        *describe_what_was_read(checkup),
        *_describe_what_running_would_cost(what, assembly, agent),
    )


def find_agent(what: WhatCouldBeRun, name: AgentName) -> AgentOnThisMachine:
    """Find what one agent answered, among everything that was read.

    :param what: Everything that was read.
    :param name: The agent to find.

    :return: What that agent said about itself here.

    :raise KeyError: When nothing was read for it, which is a reading built
        from something other than the names offgrid has adapters for.
    """
    for agent in what.agents:
        if agent.name is name:
            return agent

    raise KeyError(
        f"Nothing was read for {name.value}, so the picker cannot report on it. "
        "Every name in AgentName is asked when the screen opens."
    )


def _describe_an_agent_that_would_not_answer(
    agent: AgentOnThisMachine,
) -> tuple[str, ...]:
    """Say that an agent's own settings stopped it answering at all.

    The whole report rather than a line of it, because everything below the
    agent line is read off the agent: a report saying the rest as though it
    were true would be about a pairing that cannot be assembled.

    :param agent: The agent that would not answer.

    :return: The lines to say.
    """
    return (
        say_in_columns("agent", f"{agent.name.value}, which did not answer"),
        *say_indented(REMEDY, str(agent.unreadable)),
    )


def _as_assembled(
    profile: Profile, agent: AgentOnThisMachine, assembly: Assembly
) -> Profile:
    """Write the pairing into a profile, so the report is about that pairing.

    A copy rather than the file, because nothing here is written down: this is
    what the file would say if somebody pressed the key that saves.

    :param profile: What is written down.
    :param agent: The agent the highlight is on, and its section.
    :param assembly: What the highlight is on.

    :return: The profile the report is computed against.
    """
    # The window is carried through rather than settled: a pairing that asks
    # for no number is one the runtime answers with whatever it remembers, and
    # putting a number there would be a request nobody made.
    return profile.model_copy(
        update={
            "agent": agent.config,
            "model": ModelRequest(
                identifier=assembly.model,
                context_window=profile.model.context_window,
            ),
        }
    )


def _what_would_answer(what: WhatCouldBeRun, assembly: Assembly) -> Model | None:
    """Find the model the report's own lines are about.

    The runtime's own answer for it, so that a held model states the window it
    is served at and a cold one states only its ceiling.

    :param what: Everything that was read.
    :param assembly: What the highlight is on.

    :return: The model, or ``None`` where the pairing would run against none.
    """
    identifier = find_what_would_answer(what, assembly)

    for model in what.downloaded:
        if model.identifier == identifier:
            return model

    return None


def _describe_what_running_would_cost(
    what: WhatCouldBeRun, assembly: Assembly, agent: AgentOnThisMachine
) -> tuple[str, ...]:
    """Say what pressing a key against this pairing would do.

    One answer, most disqualifying first: a pairing whose agent is not here
    cannot be started whatever the runtime serves, and a pair that cannot talk
    is refused whether or not a load would be paid for. Saying the load beside
    a refusal would price a run that is not going to happen.

    :param what: Everything that was read.
    :param assembly: What the highlight is on.
    :param agent: The agent the highlight is on.

    :return: The lines to say.
    """
    if not agent.is_on_this_machine:
        return (
            say_in_columns(
                RUNNING,
                f"nothing here starts {agent.name.value}, so this pair cannot run",
            ),
        )

    refusal = _refuse_a_pair_that_cannot_talk(what, agent)

    if refusal is not None:
        return refusal

    if not what.downloaded:
        return _describe_a_runtime_with_nothing_downloaded(what)

    return _price_the_load(what, assembly)


def _refuse_a_pair_that_cannot_talk(
    what: WhatCouldBeRun, agent: AgentOnThisMachine
) -> tuple[str, ...] | None:
    """Say that the runtime serves nothing this agent speaks, if so.

    The refusal a run would meet, in the words a run meets it in, so that what
    is read here and what is read after committing are the same sentence — and
    it names every dialect the runtime serves, which is what says which end to
    change.

    :param what: Everything that was read.
    :param agent: The agent the highlight is on.

    :return: The lines to say, or ``None`` where the pair can talk.
    """
    terms = agent.answered.terms if agent.answered is not None else None

    if terms is None:
        return None

    try:
        require_compatible(what.runtime.served, terms.dialect)
    except DialectMismatchError as refusal:
        return (
            say_in_columns(RUNNING, "refused, and a load would not be reached"),
            *say_indented(REMEDY, str(refusal)),
        )

    return None


def _describe_a_runtime_with_nothing_downloaded(
    what: WhatCouldBeRun,
) -> tuple[str, ...]:
    """Say that the runtime has no models at all, and what to do about it.

    Its own state and its own words: an empty list is otherwise read as offgrid
    having failed to ask, and the next step is a command rather than a search.

    :param what: Everything that was read.

    :return: The lines to say.
    """
    return (
        say_in_columns(
            RUNNING,
            f"the runtime at {what.profile.runtime.host} has nothing downloaded",
        ),
        *say_indented(
            REMEDY,
            "Run `offgrid recommend` to see what this machine can hold, and how "
            "to download it.",
        ),
    )


def _price_the_load(what: WhatCouldBeRun, assembly: Assembly) -> tuple[str, ...]:
    """Say whether starting this pairing would cost a load.

    The one thing a person cannot read anywhere else before committing: a model
    already in memory answers at once, and one that is not is minutes of
    weights moving, with whatever else is held let go of first.

    :param what: Everything that was read.
    :param assembly: What the highlight is on.

    :return: The line to say.
    """
    identifier = find_what_would_answer(what, assembly)

    if identifier is None:
        return (
            say_in_columns(
                RUNNING, "no model would answer, so there is nothing to run"
            ),
        )

    if identifier in what.held:
        return (
            say_in_columns(RUNNING, f"{identifier} is held, so this costs no load"),
        )

    return (say_in_columns(RUNNING, f"{identifier} is not held, so this costs a load"),)
