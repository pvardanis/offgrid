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
from offgrid.domain.running.agent_presence import say_where_an_agent_comes_from
from offgrid.domain.running.model import Model, ModelRequest
from offgrid.shared.exceptions import AgentSettingsError
from offgrid.shared.wording import (
    UNDER,
    center_in_cells,
    describe_what_was_stated,
    pad_to_cells,
    say_indented,
)

ROW_WIDTH = 40
"""How wide a row in one of the lists may run before it breaks.

The lists are a column beside the report rather than the width of a terminal,
so a sentence on a row is broken to this rather than to the width the reports
are written to.
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

IN_MEMORY = "✅"
"""What marks a model the runtime is already holding.

A mark rather than the word, because the column is called `held` and a column
whose every filled cell repeats its own heading says nothing twice. Held models
sort first, so the marks are one block at the top that an eye finds without
reading.

Two cells wide, like most emoji, which is why the row is padded by what it
takes on a terminal rather than by how many characters it has.
"""


@dataclass(frozen=True)
class WouldNotAnswer:
    """Why an agent's own settings stopped it saying anything about itself.

    :param why: What stopped it, as the person reading the screen is told.
    """

    why: str


@dataclass(frozen=True)
class AgentOnThisMachine:
    """One agent offgrid has an adapter for, and what it answered here.

    Every agent offgrid drives is here whether or not the machine has it, so
    that the list is what offgrid supports rather than what happens to be
    installed. What is absent is marked rather than left out.

    An agent either answered or said why it could not, which is one field of
    two types rather than two fields that must disagree: a pair of them can be
    built both set and both empty, and the row and the report each have to
    decide what those mean.

    :param config: What its section of a profile would hold, which is the
        profile's own where the profile names this agent.
    :param answered: What it said about itself, or what stopped it. An agent
        whose own settings will not read is a row a person can see and not
        pick, rather than a screen that will not open.
    """

    config: AgentConfig
    answered: WhatTheAgentAnswered | WouldNotAnswer

    @property
    def name(self) -> AgentName:
        """Which agent this is, as a profile names it.

        Read off the config rather than stored beside it, so that a reading
        cannot be built claiming to be about an agent it did not ask.

        :return: The name.
        """
        return self.config.name

    @property
    def is_on_this_machine(self) -> bool:
        """Whether a run could start this agent as things stand.

        :return: Whether it answered, and whether the `PATH` has its command.
        """
        return (
            isinstance(self.answered, WhatTheAgentAnswered)
            and self.answered.found_at is not None
        )


@dataclass(frozen=True)
class WhatCouldBeRun:
    """Everything a person picks from, read before any of it is shown.

    :param profile: What is written down, which is what the picker starts
        assembled as.
    :param runtime: What the runtime answered, the model it is holding
        included.
    :param downloaded_models: Every model the runtime has, held or not, in the order
        it answered in. `order_models_held_first` is what puts the held ones
        at the top of a list; the port promises no order here.
    :param held: Which of them are in memory, so that a pairing can be priced
        without asking again.
    :param agents: Every agent offgrid drives, and what each said here.
    """

    profile: Profile
    runtime: WhatTheRuntimeAnswered
    downloaded_models: tuple[Model, ...]
    held: frozenset[str]
    agents: tuple[AgentOnThisMachine, ...]


@dataclass(frozen=True)
class Pairing:
    """The agent and model a highlight is sitting on.

    :param agent: The agent that would be started.
    :param model: The model that would answer, or ``None`` where the pairing
        asks for nothing and takes whatever the runtime is holding — which is
        what a profile naming no model says, and what the picker opens on.
    """

    agent: AgentName
    model: str | None


def order_models_held_first(report: WhatCouldBeRun) -> tuple[Model, ...]:
    """Put the models that cost nothing to start at the top of the list.

    Held first and each group in the order the runtime answered in, so that
    two readings of an unchanged machine list them alike.

    :param report: Everything that was read.

    :return: Every model downloaded, the held ones first.
    """
    return tuple(
        sorted(
            report.downloaded_models,
            key=lambda model: model.identifier not in report.held,
        )
    )


def open_on_what_the_profile_holds(report: WhatCouldBeRun) -> Pairing:
    """Say what the picker is assembled as before anybody presses a key.

    The file itself, so that the first thing shown is what a run would do
    today. A profile naming no model keeps naming none: the highlight lands on
    the model that would answer, and sitting on a row is not the same statement
    as having written its name down.

    :param report: Everything that was read.

    :return: The pairing the file holds.
    """
    return Pairing(
        agent=report.profile.agent_name,
        model=report.profile.model.identifier,
    )


def find_what_would_answer(report: WhatCouldBeRun, pairing: Pairing) -> str | None:
    """Name the model a pairing would run against, which may be none.

    A pairing naming no model takes whatever the runtime is holding, so the row
    to sit on is the resident one. Where nothing is held either, there is no
    row to sit on.

    :param report: Everything that was read.
    :param pairing: What the highlight is on.

    :return: The model's identifier, or ``None`` where none would answer.
    """
    if pairing.model is not None:
        return pairing.model

    resident = report.runtime.resident

    return resident.identifier if resident is not None else None


def read_the_highlight(
    report: WhatCouldBeRun, *, agent: str | None, model: str | None
) -> Pairing:
    """Read what the highlights are sitting on as a pairing.

    Either list can have no reachable row — every agent absent, or nothing
    downloaded — and nowhere to sit is not a statement about what to run. Both
    fall back on what the profile names, so that a machine with no agent
    installed still reports on the one a run would try to start, and a runtime
    with an empty catalogue still reports the model the file asks for.

    A profile that names no model, with the highlight on the model the runtime
    is already holding, still names none: the two describe the same run today,
    and the difference is only what a save would write down. A profile that
    does name one is left alone, because there the highlight and the file are
    two statements and the highlight is the one a person just made.

    :param report: Everything that was read.
    :param agent: What the agent list's highlight is on, or ``None`` where the
        list has no row a cursor can reach.
    :param model: What the model list's highlight is on, or ``None`` where the
        list has no row a cursor can reach.

    :return: The pairing to report on.
    """
    named = open_on_what_the_profile_holds(report)

    resident = report.runtime.resident
    sitting_on_the_resident = resident is not None and model == resident.identifier
    takes_what_is_held = sitting_on_the_resident and named.model is None

    return Pairing(
        agent=named.agent if agent is None else AgentName(agent),
        model=named.model if model is None or takes_what_is_held else model,
    )


def assemble_a_profile(report: WhatCouldBeRun, pairing: Pairing) -> Profile:
    """Write what a highlight is on into the profile it would be saved as.

    A copy of the file with the pairing's agent and model in it: what the file
    would say if the key that writes were pressed, and what a run reached from
    the screen is made from whether or not it is written.

    The window is carried through rather than settled. A pairing that asks for
    no number is one the runtime answers with whatever it remembers, and
    materialising it into a number is a request nobody made — the one thing a
    save must not quietly write.

    :param report: Everything that was read.
    :param pairing: What the highlights are on.

    :return: The profile the pairing assembles to.

    :raise AgentSettingsError: When nothing was read for the pairing's agent,
        which is offgrid's own fault rather than this machine's — every name in
        `AgentName` is asked when the screen opens.
    """
    return report.profile.model_copy(
        update={
            "agent": find_agent(report, pairing.agent).config,
            "model": ModelRequest(
                identifier=pairing.model,
                context_window=report.profile.model.context_window,
            ),
        }
    )


def describe_what_a_save_wrote(profile: Profile) -> str:
    """Say what a save put in the file, which is wider than the model alone.

    Claude Code's picker writes one field; a save here writes runtime, agent
    and model, so a person trying an agent once has rewritten three keys. The
    sentence names all of them rather than only the model, so a wider write is
    never a silent one.

    :param profile: What was saved.

    :return: The line a person reads after a save.
    """
    named = profile.model.identifier
    model = named if named is not None else "no model, so a run takes whatever is held"

    return (
        f"Saved to your profile: runtime {profile.runtime_name.value}, "
        f"agent {profile.agent_name.value}, model {model}."
    )


def describe_an_agent_row(agent: AgentOnThisMachine) -> str:
    """Lay out the row one agent is listed as.

    An agent this machine has not got is marked on the row rather than left
    out, because the list is also how a person learns what offgrid supports.

    Why it is marked goes on the row too, under the name, because the cursor
    steps over such a row and the report is only ever computed for the row the
    cursor is on: said anywhere else, the one sentence that helps is the one
    sentence nobody can reach. It is wrapped to the list rather than to the
    report's own width, since it is read in a narrower column.

    :param agent: The agent to lay out.

    :return: The row, as it is read, over as many lines as it takes.
    """
    if isinstance(agent.answered, WouldNotAnswer):
        return _mark_an_agent_row(agent.name, "did not answer", agent.answered.why)

    if not agent.is_on_this_machine:
        return _mark_an_agent_row(
            agent.name, "not installed", say_where_an_agent_comes_from(agent.name)
        )

    return agent.name.value


def _mark_an_agent_row(name: AgentName, marked: str, why: str) -> str:
    """Lay out an agent that cannot be picked, with the reason under it.

    :param name: The agent.
    :param marked: What is wrong with it, in the column beside its name.
    :param why: What to do about it, or what stopped it.

    :return: The row, over as many lines as the reason takes.
    """
    return "\n".join(
        (f"{name.value:<{AGENT_COLUMN}}{marked}", *say_indented(UNDER, why, ROW_WIDTH))
    )


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
        IN_MEMORY if held else "",
        describe_what_was_stated(model.context_ceiling),
    )


def name_the_model_columns() -> str:
    """Name what each column of a model row holds.

    A bare number in a list is a number about nothing: a person scanning
    262144 against 40960 has to already know which of a model's two context
    figures they are reading. The `context` column is its ceiling — the figure
    that exists whether or not anything has loaded the model, where the other
    one does not exist until it is served.

    Laid out by the same call the rows are, so that a column that moves cannot
    leave its own name behind.

    :return: The heading, laid out in the columns the rows are.
    """
    return _lay_out_a_model_row("model", "held", "context")


def _lay_out_a_model_row(identifier: str, held: str, ceiling: str) -> str:
    """Put three values in the columns a model is listed in.

    Padded by what each takes on a terminal rather than by how many characters
    it has, because the mark for a held model is one character and two cells:
    counted the other way, every held row would sit one place to the left of
    every cold one. The mark is centred in its column so that it and the `held`
    heading over it share a centre rather than a left edge.

    :param identifier: What the model is called.
    :param held: What marks it as in memory, or empty where it is not.
    :param ceiling: The most it could ever be served at.

    :return: The line, as it is read.
    """
    laid_out = (
        pad_to_cells(identifier, MODEL_COLUMN),
        center_in_cells(held, HELD_COLUMN),
        ceiling,
    )

    return "".join(laid_out).rstrip()


def find_agent(report: WhatCouldBeRun, name: AgentName) -> AgentOnThisMachine:
    """Find what one agent answered, among everything that was read.

    :param report: Everything that was read.
    :param name: The agent to find.

    :return: What that agent said about itself here.

    :raise AgentSettingsError: When nothing was read for it, which is a reading
        built from something other than the names offgrid has adapters for.
        offgrid's own error rather than a `KeyError`, so that the sentence
        reaches a person as written instead of quoted and escaped.
    """
    for agent in report.agents:
        if agent.name is name:
            return agent

    raise AgentSettingsError(
        f"Nothing was read for {name.value}, so the picker cannot report on it. "
        "Every name in AgentName is asked when the screen opens, which makes "
        "this a fault in offgrid rather than in this machine."
    )
