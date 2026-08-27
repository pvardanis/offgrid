"""What could be run on this machine, and how a person picks their way through it.

Everything is read once, and everything after that is composed out of what came
back. Moving a highlight reaches no runtime, opens no file and writes nothing,
which is what makes looking around free.

What one pairing would report and cost is `costing.py`, which reaches for these
values. Nothing here reaches back: this is the list of what there is, and that
is what one of them would do.

A pairing names an agent and a model and not a runtime, because there is one
runtime adapter and its config is the profile's. The list shows it, so that a
person can see what offgrid drives; the day there are two, this is where the
second one lands.
"""

from dataclasses import dataclass

from offgrid.domain.checkup import WhatTheAgentAnswered, WhatTheRuntimeAnswered
from offgrid.domain.profile import Profile
from offgrid.domain.running.agent import AgentConfig, AgentName
from offgrid.domain.running.model import Model
from offgrid.shared.wording import describe_what_was_stated

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

    A profile that names no model, with the highlight on the model the runtime
    is already holding, still names none: the two describe the same run today,
    and the difference is only what a save would write down. A profile that
    does name one is left alone, because there the highlight and the file are
    two statements and the highlight is the one a person just made.

    :param what: Everything that was read.
    :param agent: What the agent list's highlight is on, or ``None`` for none.
    :param model: What the model list's highlight is on, or ``None`` for none.

    :return: The pairing to report on.
    """
    if agent is None:
        return open_on_what_the_profile_holds(what)

    resident = what.runtime.resident
    sitting_on_the_resident = resident is not None and model == resident.identifier
    asks_for_nothing = what.profile.model.identifier is None

    return Assembly(
        agent=AgentName(agent),
        model=None if sitting_on_the_resident and asks_for_nothing else model,
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
    return _lay_out_a_model_row(
        model.identifier,
        "held" if held else "",
        describe_what_was_stated(model.context_ceiling),
    )


def name_the_model_columns() -> str:
    """Name what each column of a model row holds.

    A bare number in a list is a number about nothing: a person scanning
    262144 against 40960 has to already know which of a model's two context
    figures they are reading, and the whole reason the ceiling is here is that
    the other one does not exist until something loads the model.

    Beside the row it heads rather than in the screen, so that a column that
    moves cannot leave its own name behind.

    :return: The heading, laid out in the columns the rows are.
    """
    return _lay_out_a_model_row("model", "held", "ceiling")


def _lay_out_a_model_row(identifier: str, held: str, ceiling: str) -> str:
    """Put three values in the columns a model is listed in.

    :param identifier: What the model is called.
    :param held: Whether it is in memory, or empty where it is not.
    :param ceiling: The most it could ever be served at.

    :return: The line, as it is read.
    """
    return f"{identifier:<{MODEL_COLUMN}}{held:<{HELD_COLUMN}}{ceiling}".rstrip()


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
