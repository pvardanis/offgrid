"""What the run panel says about one pairing, in the screen's own voice.

The picker is a decision made in the moment before a key is pressed, not the
diagnosis `doctor` prints, so it words a run its own compact way rather than
reprinting that report. What the two surfaces share is the source of truth —
the model's numbers, the agent's `Conversations`, the dialect check, and the
`Tone` a pairing sorts into — not the phrasing.

Two parts, read by two questions. The signal is what a person decides on:
whether starting the pairing costs a load, the context it would be served at,
whether the pair can talk, and where a conversation it starts would be kept.
The detail, behind a collapsible, is a curated summary of what a run was told:
the runtime, the request, the agent's floor, any discarded window, and the
dialect the pair agrees on.

Apart from `assembling.py` because the two are read by different questions —
what there is to pick from, and what one pick would do — and because the
dependency runs one way: this reaches for those values and they know nothing
about this.
"""

from dataclasses import dataclass
from enum import Enum

from offgrid.domain.assembling import (
    AgentOnThisMachine,
    Pairing,
    WhatCouldBeRun,
    WouldNotAnswer,
    assemble_a_profile,
    find_agent,
    find_what_would_answer,
)
from offgrid.domain.checkup import WhatTheAgentAnswered, WhatTheRuntimeAnswered
from offgrid.domain.running.agent import AgentName
from offgrid.domain.running.conversations import Conversations
from offgrid.domain.running.dialect import Dialect, require_compatible
from offgrid.domain.running.leaving import Reading
from offgrid.domain.running.model import Model, ModelRequest
from offgrid.shared.exceptions import DialectMismatchError
from offgrid.shared.wording import describe_what_was_stated

_LABEL = 10
"""How wide the detail's label column is, the longest label plus a space.

Its own narrow width rather than the report's, because the detail is a summary
a person glances down rather than the column `doctor` prints. Every value, a
top label's and a nested one's alike, begins at this column, so the detail
reads as one aligned column however deep a line sits.
"""

_SUBINDENT = "  "
"""How far a line nested under one of the detail's is indented.

The command, the ways off the machine and the dialect are the agent's, so they
sit indented under it — but their values still begin at `_LABEL`, so the indent
shows the nesting without opening a second value column beside the first.
"""


class Tone(Enum):
    """How a signal line reads at a glance, before its words are.

    The four verdicts a person weighing a run sorts a line into: it is fine, it
    is barred, it will cost something, or it is a fact with no verdict. A
    surface paints each its own way; the domain only says which it is, so two
    surfaces cannot colour one verdict differently.
    """

    OK = "ok"
    """A run that would start and cost no load."""

    BLOCKED = "blocked"
    """A pairing that cannot run at all, whatever else is true."""

    COST = "cost"
    """A run that would start, but only after a load is paid for."""

    INFO = "info"
    """A fact read beside the verdict, carrying none of its own."""


@dataclass(frozen=True)
class SignalLine:
    """One line of the run signal, and how it reads at a glance.

    :param text: What the line says.
    :param tone: The verdict it carries, which a surface paints it by.
    """

    text: str
    tone: Tone


@dataclass(frozen=True)
class RunningCost:
    """What starting a pairing would cost, and whether it can be started at all.

    :param lines: The words for it, as the signal reads them.
    :param tone: Whether it would run for free, run at a cost, or not run.
    """

    lines: tuple[str, ...]
    tone: Tone


def describe_the_signal(
    report: WhatCouldBeRun, pairing: Pairing
) -> tuple[SignalLine, ...]:
    """Say, in a few lines that read at a glance, what this pairing would do.

    The part of a run a person decides on before committing: whether it costs a
    load, the context it would be served at against its ceiling, whether the
    pair can talk, and where a conversation it starts would be kept. A pairing
    that cannot run says only why; there is no context to weigh behind a bar.

    :param report: Everything that was read.
    :param pairing: What the highlight is on.

    :return: The signal lines, each carrying the verdict a surface paints it by.
    """
    agent = find_agent(report, pairing.agent)
    answered = agent.answered

    if isinstance(answered, WouldNotAnswer):
        return (
            SignalLine(
                f"{agent.name.value}, which did not answer, so this pair cannot run",
                Tone.BLOCKED,
            ),
            *_toned(tuple(answered.why.split("\n")), Tone.BLOCKED),
        )

    cost = _reckon_what_running_would_cost(
        report, pairing, agent, answered.terms.dialect
    )

    if cost.tone is Tone.BLOCKED:
        return _toned(cost.lines, Tone.BLOCKED)

    model = _find_the_model_that_would_answer(report, pairing)
    held = model is not None and model.identifier in report.held

    return (
        *_toned(cost.lines, cost.tone),
        SignalLine(_describe_the_served_context(model, held=held), Tone.INFO),
        SignalLine(
            _describe_whether_the_pair_can_talk(agent.name, answered.terms.dialect),
            Tone.INFO,
        ),
        SignalLine(_describe_conversations(answered.kept), Tone.INFO),
    )


def describe_the_detail(report: WhatCouldBeRun, pairing: Pairing) -> tuple[str, ...]:
    """Put the fuller telling of a run into the lines the collapsible reads.

    The whole of what a run was told, in the screen's own compact words rather
    than `doctor`'s column report: the runtime and what it serves, the agent's
    floor, the command that starts it and where it lives, what a run could send
    off this machine, the dialect the pair agrees on, any window offgrid stopped
    asking for, and — last — the model asked for against the context it could
    run in.

    The agent's own lines wait on it having answered — nothing is said about the
    command, the ways off the machine or the dialect of an agent whose settings
    would not read.

    :param report: Everything that was read.
    :param pairing: What the highlight is on.

    :return: The detail lines, in the order they are read.
    """
    agent = find_agent(report, pairing.agent)
    answered = agent.answered
    requested = assemble_a_profile(report, pairing).model
    model = _find_the_model_that_would_answer(report, pairing)

    lines = [_detail_line("runtime", _describe_the_runtime(report))]

    if isinstance(answered, WhatTheAgentAnswered):
        floor = answered.terms.context_floor
        lines.append(_detail_line("agent", f"minimum required context {floor}"))
        lines.append(_under_agent("command", _describe_the_command(answered)))
        lines.extend(_describe_what_might_leave(answered.could_leave))
        lines.append(
            _under_agent(
                "dialect",
                _describe_the_dialect(answered.terms.dialect, report.runtime.served),
            )
        )

    lines.extend(_describe_a_discarded_window(report.runtime))
    lines.append(_detail_line("model", _describe_the_model(model, requested)))

    return tuple(lines)


def _toned(lines: tuple[str, ...], tone: Tone) -> tuple[SignalLine, ...]:
    """Give a run of lines the one verdict they share.

    :param lines: The lines to tag.
    :param tone: The verdict all of them carry.

    :return: One `SignalLine` per line, each carrying that verdict.
    """
    return tuple(SignalLine(line, tone) for line in lines)


def _detail_line(label: str, value: str) -> str:
    """Lay one detail line out, its label in the narrow column the summary uses.

    :param label: What the line is about.
    :param value: What it says.

    :return: The label padded to the column, then the value.
    """
    return f"{label:<{_LABEL}}{value}"


def _under_agent(label: str, value: str) -> str:
    """Lay a line out nested under the agent's, with its own narrower label.

    :param label: What the nested line is about.
    :param value: What it says.

    :return: The indent, the label padded so its value begins at ``_LABEL``,
        then the value.
    """
    return f"{_SUBINDENT}{label:<{_LABEL - len(_SUBINDENT)}}{value}"


def _describe_the_served_context(model: Model | None, *, held: bool) -> str:
    """Say the context a model would run in: what it is served at, and its most.

    A held model is being served at a window now; a cold one is not being served
    at all, so it has a ceiling and no window yet.

    :param model: The model that would answer, or ``None`` for none.
    :param held: Whether the runtime has it in memory.

    :return: The line to say.
    """
    if model is None:
        return "context unknown"

    ceiling = describe_what_was_stated(model.context_ceiling)

    if held:
        window = describe_what_was_stated(model.context_window)

        return f"served at context {window} (context ceiling {ceiling})"

    return f"context ceiling {ceiling}"


def _describe_whether_the_pair_can_talk(name: AgentName, dialect: Dialect) -> str:
    """Say the pair can talk, and the shape they agree on.

    Reached only where they can — a pair that cannot is barred by the cost
    reckoning before the signal reaches here.

    :param name: The agent that would start.
    :param dialect: The shape it speaks, which the runtime serves.

    :return: The line to say.
    """
    return f"{name.value} · pair can talk ({dialect.value})"


def _describe_conversations(kept: Conversations) -> str:
    """Say where a conversation this run starts lands, and the way back in.

    Only the directory and the commands that reopen one — the provenance and
    the finding `doctor` carries are left out of a line read at a glance.

    :param kept: Where the agent keeps them, and how to open one again.

    :return: The line to say.
    """
    return f"conversations → {kept.kept_in} (offgrid's own; {kept.resume_with})"


def _describe_the_runtime(report: WhatCouldBeRun) -> str:
    """Say which runtime a run reaches, and every shape it serves.

    :param report: Everything that was read.

    :return: The line to say.
    """
    runtime = report.profile.runtime
    served = " + ".join(sorted(dialect.value for dialect in report.runtime.served))

    return f"{runtime.name.value} at {runtime.host}, serves {served}"


def _describe_the_model(model: Model | None, request: ModelRequest) -> str:
    """Say the model a run asks for against the context it could run in.

    One line: which model (or that a run takes whatever is held), the ceiling
    that exists whether or not it is loaded, and the context a run would ask to
    hold it at — or that it would inherit whatever is served.

    :param model: The model that would answer, or ``None`` for none.
    :param request: What the run will ask for.

    :return: The line to say.
    """
    ceiling = describe_what_was_stated(model.context_ceiling) if model else "unknown"

    if request.context_window is None:
        requested = "inherit served"
    else:
        requested = str(request.context_window)

    if request.identifier is not None:
        asked = request.identifier
    else:
        asked = "no model, so a run takes whatever is held"

    return f"{asked}, context ceiling {ceiling}, requested context {requested}"


def _describe_the_command(answered: WhatTheAgentAnswered) -> str:
    """Say the command a run would start, and where the `PATH` has it.

    :param answered: What the agent said, and where its command was found.

    :return: The line to say.
    """
    command = answered.terms.command

    if answered.found_at is not None:
        return f"{command}, at {answered.found_at}"

    return f"{command}, not on PATH"


def _describe_what_might_leave(readings: tuple[Reading, ...]) -> tuple[str, ...]:
    """Say what a run could send off this machine, one line for each way.

    A reading each — hosted tools, transcript sharing — under the `leaving`
    label the agent's block gives them, the first on that line and the rest
    aligned under it, so a person reads which of them each state is about.

    :param readings: What the agent said about each way off this machine.

    :return: The lines to say.
    """
    column = max(len(reading.subject) for reading in readings) + 2
    indent = " " * _LABEL
    first, *rest = readings

    return (
        _under_agent("leaving", f"{first.subject:<{column}}{first.status}"),
        *(f"{indent}{reading.subject:<{column}}{reading.status}" for reading in rest),
    )


def _describe_the_dialect(dialect: Dialect, served: frozenset[Dialect]) -> str:
    """Say the shape the agent speaks, against the set the runtime serves.

    :param dialect: The shape the agent expects.
    :param served: Every shape the runtime serves.

    :return: The line to say.
    """
    serves = ", ".join(sorted(shape.value for shape in served))

    return f"agent speaks {dialect.value} ∈ {{{serves}}}"


def _describe_a_discarded_window(runtime: WhatTheRuntimeAnswered) -> tuple[str, ...]:
    """Say that offgrid stopped asking for a window, where it did.

    Nothing where no window was discarded, since the summary says only what
    happened. A record that could not be read is itself a line.

    :param runtime: What the runtime answered.

    :return: A line for each discarded window, or none.
    """
    if runtime.unreadable is not None:
        return (_detail_line("discarded", runtime.unreadable),)

    return tuple(
        _detail_line(
            "discarded",
            f"context {record.asked_for} refused, {record.served} served "
            f"on {record.dated}",
        )
        for record in runtime.discarded
    )


def _find_the_model_that_would_answer(
    report: WhatCouldBeRun, pairing: Pairing
) -> Model | None:
    """Find the model the signal's numbers are about.

    The runtime's own answer for it, so that a held model states the window it
    is served at and a cold one states only its ceiling.

    :param report: Everything that was read.
    :param pairing: What the highlight is on.

    :return: The model, or ``None`` where the pairing would run against none.
    """
    identifier = find_what_would_answer(report, pairing)

    for model in report.downloaded_models:
        if model.identifier == identifier:
            return model

    return None


def _reckon_what_running_would_cost(
    report: WhatCouldBeRun,
    pairing: Pairing,
    agent: AgentOnThisMachine,
    speaks: Dialect,
) -> RunningCost:
    """Say what pressing a key against this pairing would do, and how it reads.

    One answer, most disqualifying first: a pairing whose agent is not here
    cannot be started whatever the runtime serves, and a pair that cannot talk
    is refused whether or not a load would be paid for. Saying the load beside
    a refusal would price a run that is not going to happen.

    The verdict rides with the words: everything that bars a run is `BLOCKED`,
    and only a load that would be paid, or saved, tells `COST` from `OK`.

    :param report: Everything that was read.
    :param pairing: What the highlight is on.
    :param agent: The agent the highlight is on.
    :param speaks: The shape that agent expects, read where it was known to
        have answered at all.

    :return: The lines to say, and the verdict they carry.
    """
    if not agent.is_on_this_machine:
        return RunningCost(
            (f"nothing here starts {agent.name.value}, so this pair cannot run",),
            Tone.BLOCKED,
        )

    refusal = _refuse_a_pair_that_cannot_talk(report, speaks)

    if refusal is not None:
        return RunningCost(refusal, Tone.BLOCKED)

    host = report.profile.runtime_host

    if not report.downloaded_models:
        return RunningCost(
            (
                f"the runtime at {host} has nothing downloaded",
                "Run `offgrid recommend` to see what fits, and how to download it.",
            ),
            Tone.BLOCKED,
        )

    identifier = find_what_would_answer(report, pairing)

    if identifier is None:
        return RunningCost(
            ("no model would answer, so there is nothing to run",), Tone.BLOCKED
        )

    if _find_the_model_that_would_answer(report, pairing) is None:
        return RunningCost(
            (
                f"the runtime at {host} has not got {identifier}",
                "Pick a listed model, or name a downloaded one in the profile.",
            ),
            Tone.BLOCKED,
        )

    runtime = report.profile.runtime.name.value

    if identifier in report.held:
        return RunningCost(
            (f"{identifier} is held by {runtime}, so this costs no load",), Tone.OK
        )

    return RunningCost(
        (f"{identifier} is not held by {runtime}, so this costs a load",), Tone.COST
    )


def _refuse_a_pair_that_cannot_talk(
    report: WhatCouldBeRun, speaks: Dialect
) -> tuple[str, ...] | None:
    """Say that the runtime serves nothing this agent speaks, if so.

    The refusal a run would meet, in the words a run meets it in, so that what
    is read here and what is read after committing are the same sentence — and
    it names every dialect the runtime serves, which is what says which end to
    change.

    :param report: Everything that was read.
    :param speaks: The shape the agent the highlight is on expects.

    :return: The lines to say, or ``None`` where the pair can talk.
    """
    try:
        require_compatible(report.runtime.served, speaks)
    except DialectMismatchError as refusal:
        return ("refused, and a load would not be reached", str(refusal))

    return None
