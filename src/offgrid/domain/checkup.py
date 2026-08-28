"""What a run can be told before it costs a load, and how it reads."""

from dataclasses import dataclass
from pathlib import Path

from offgrid.domain.profile import Profile
from offgrid.domain.running import discarded_windows
from offgrid.domain.running.agent import AgentTerms
from offgrid.domain.running.agent_presence import say_where_an_agent_comes_from
from offgrid.domain.running.asking import describe_what_is_asked_for
from offgrid.domain.running.conversations import Conversations
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.discarded_windows import DiscardedWindow
from offgrid.domain.running.leaving import Reading, Status
from offgrid.domain.running.model import Model, ModelRequest
from offgrid.shared.wording import (
    REMEDY,
    UNDER,
    describe_what_was_stated,
    say_in_columns,
    say_indented,
)

HELD_NOTHING = say_in_columns("model", "nothing held")


@dataclass(frozen=True)
class WhatTheRuntimeAnswered:
    """What the runtime said, and what offgrid keeps about it.

    :param resident: The model it is holding, or ``None`` where it holds none
        — which the rest of the report survives, because a runtime holding
        nothing still answered.
    :param served: Every dialect it serves, which says whether an agent other
        than this one would pair with it.
    :param discarded: Every window it discarded for the model it is holding,
        and empty where it discarded none and where the records could not be
        read — which is itself a finding, carried in `unreadable`.
    :param unreadable: Why the records could not be read, where they could not.
        A stale file nobody has heard of is worth a line, not the whole report.
    """

    resident: Model | None
    served: frozenset[Dialect]
    discarded: tuple[DiscardedWindow, ...]
    unreadable: str | None


@dataclass(frozen=True)
class WhatTheAgentAnswered:
    """What the agent said, and what this machine says about it.

    `found_at` is the odd one: it is a fact about the machine rather than
    about the agent. It is here because it is the answer to a question about
    the agent, and reading it beside the command it was looked up from is
    what keeps the two from being about different agents.

    :param terms: What it states about itself — the dialect it speaks, the
        window it will not start below, and the command that starts it.
    :param found_at: Where the `PATH` a run inherits has that command, and
        ``None`` where it has not got it at all.
    :param could_leave: What it says about each way this run could reach off
        this machine, one reading each.
    :param kept: Where it keeps a conversation a run starts, and how to open
        one again — which nothing outside a run finds.
    """

    terms: AgentTerms
    found_at: Path | None
    could_leave: tuple[Reading, ...]
    kept: Conversations


@dataclass(frozen=True)
class Checkup:
    """Everything `doctor` read, including what it found nothing to read.

    One value per thing that answered, which is the sentence `doctor` is: the
    profile, the runtime and the agent. Readings rather than the things
    themselves — the agent port can write its own settings, and a value the
    report is built from has no call to carry the means of doing it.

    :param profile: What was written down.
    :param runtime: What the runtime answered.
    :param agent: What the agent answered.
    """

    profile: Profile
    runtime: WhatTheRuntimeAnswered
    agent: WhatTheAgentAnswered


def describe_what_was_read(checkup: Checkup) -> tuple[str, ...]:
    """Put the report into the lines it is read as.

    A value rather than a run of statements that each print, so what the
    report says is settled in one place and said in another.

    :param checkup: What the profile, the runtime and the agent answered.

    :return: The lines to say, in the order they are read.
    """
    # Three things answered, and what each of them said sits under it: the
    # runtime and what it serves, the model and the two numbers about it, the
    # agent and what starting it takes. Read down the left, a person meets one
    # thing at a time rather than eleven facts in a column.
    #
    # The model it names is the one the runtime is holding, so it is held by
    # construction: a runtime holding nothing takes the other branch.
    return (
        *describe_the_runtime(checkup.profile, checkup.runtime),
        *describe_the_model(checkup.runtime.resident, checkup.profile.model, held=True),
        *describe_what_is_requested(checkup),
        *describe_the_agent(checkup),
        *describe_a_discarded_window(checkup.runtime),
    )


def describe_the_runtime(
    profile: Profile, answered: WhatTheRuntimeAnswered
) -> tuple[str, ...]:
    """Say which runtime answered, and every shape it serves.

    It takes the two things it reads rather than the whole reading, because a
    surface reporting on an agent that would not answer has no `Checkup` to
    hand and is still owed these lines: what the runtime said is true whatever
    the agent did.

    :param profile: What was written down.
    :param answered: What the runtime said.

    :return: The lines to say.
    """
    runtime = profile.runtime

    return (
        say_in_columns("runtime", f"{runtime.name.value} at {runtime.host}, reachable"),
        say_in_columns(
            "dialects",
            ", ".join(sorted(d.value for d in answered.served)),
            under=True,
        ),
    )


def describe_what_is_requested(checkup: Checkup) -> tuple[str, ...]:
    """Say what the next run asks the runtime for.

    :param checkup: What the profile, the runtime and the agent answered.

    :return: The line to say.
    """
    return (
        say_in_columns("requests", describe_what_is_asked_for(checkup.profile.model)),
    )


def describe_the_agent(checkup: Checkup) -> tuple[str, ...]:
    """Say which agent would start, what starting it takes, and what it keeps.

    :param checkup: What the profile, the runtime and the agent answered.

    :return: The lines to say, in the order they are read.
    """
    terms = checkup.agent.terms

    return (
        say_in_columns(
            "agent",
            f"{checkup.profile.agent_name.value}, speaking {terms.dialect.value}",
        ),
        *_describe_where_the_agent_is(checkup),
        say_in_columns("context_minimum", str(terms.context_floor), under=True),
        *_describe_what_could_leave(checkup.agent.could_leave),
        *_describe_where_conversations_are_kept(checkup.agent.kept),
    )


def _describe_where_the_agent_is(checkup: Checkup) -> tuple[str, ...]:
    """Say the command a run would start, and where the `PATH` has it.

    Said at all because the alternative is exit 127, met after a model has
    been loaded and let go again for a run that was never going to start.

    Where it comes from goes under the line it is about, where a reading about
    what could leave puts its remedy. A link and not a command to type, for
    the reason `agent_presence.py` gives.

    :param checkup: What was read, the profile it names the agent in included.

    :return: The command's line, and where to get it where it is not here.
    """
    command = checkup.agent.terms.command

    if checkup.agent.found_at is not None:
        return (
            say_in_columns(
                "command", f"{command}, at {checkup.agent.found_at}", under=True
            ),
        )

    return (
        say_in_columns("command", f"{command}, not on PATH", under=True),
        *say_indented(
            REMEDY, say_where_an_agent_comes_from(checkup.profile.agent_name)
        ),
    )


def _describe_what_could_leave(readings: tuple[Reading, ...]) -> tuple[str, ...]:
    """Say what each way off this machine is in, and how to close an open one.

    One line per reading under one heading, so the report says which of them
    it is telling somebody about and a person reads the pair as one question
    rather than as two facts that happen to share a word. What a run would
    refuse with goes under the line it is about — said here instead of after
    the load the command was run to save.

    `DENIED` alone says no more than the state, because that is the one answer
    with nothing behind it to check and nothing to act on: the lines beside it
    are what somebody came for. `NONE_OFFERED` says its detail, because a claim
    that an agent has no such thing is only worth what the evidence beside it
    is, and this report is where a person reads that evidence.

    :param readings: What the agent said about each way off this machine.

    :return: The lines to say, in the order the agent answered them.
    """
    said: tuple[str, ...] = ("might leave this machine",)

    # A column of their own, because what a subject is called is one agent's
    # business and the longest of them is longer than any label in the report.
    # Read against each other is how a person tells one state from the other.
    column = max(len(reading.subject) for reading in readings) + 2

    for reading in readings:
        said = (*said, f"{UNDER}{reading.subject:<{column}}{reading.status}")

        if reading.status is not Status.DENIED:
            said = (*said, *say_indented(REMEDY, reading.said))

    return said


def _describe_where_conversations_are_kept(kept: Conversations) -> tuple[str, ...]:
    """Say where a conversation this run starts lands, and the way back into it.

    On every run rather than where an installation is kept apart, because there
    is no second case: every agent offgrid runs is run out of a directory of
    offgrid's, so a branch with one arm would claim a kind of agent that does
    not exist.

    The way back goes under the directory, where a reading about what could
    leave puts its remedy: a directory on its own is what a person already had.

    :param kept: Where the agent keeps them, and how to open one again.

    :return: The lines to say, in the order they are read.
    """
    # Both at the same indent, because they are two halves of one answer
    # rather than a fact and a remedy: the directory is where a conversation
    # lands, and the sentence is how it is opened again.
    return (
        "conversations",
        f"{UNDER}{kept.kept_in}",
        *say_indented(UNDER, kept.said),
    )


def describe_the_model(
    model: Model | None, request: ModelRequest, *, held: bool
) -> tuple[str, ...]:
    """Say which model would answer, and at what, or that none would.

    A runtime holding nothing keeps its lines in the column, the two numbers
    marked `unknown` rather than left out: a number about a model that is not
    held is unknown, where `unstated` is what a held model states when the
    runtime says no number for it. The same distinction decides the window of a
    model that is downloaded and cold — nothing is serving it, so the number
    does not exist yet rather than having gone unsaid.

    :param model: The model that would answer, or ``None`` for none.
    :param request: What the profile asks the next run for, which decides
        whether a runtime holding nothing needs a hand.
    :param held: Whether the runtime has that model in memory. `doctor` reads
        its model off what is held, so it says so; a screen reporting on a
        model somebody is only looking at does not.

    :return: The model's lines, and what to do about a runtime holding
        nothing where the profile names none either.
    """
    if model is not None:
        return (
            say_in_columns("model", model.identifier),
            say_in_columns(
                "context_ceiling",
                describe_what_was_stated(model.context_ceiling),
                under=True,
            ),
            say_in_columns(
                "context_window",
                describe_what_was_stated(model.context_window) if held else "unknown",
                under=True,
            ),
        )

    unknown = (
        say_in_columns("context_ceiling", "unknown", under=True),
        say_in_columns("context_window", "unknown", under=True),
    )

    # `settle_what_to_run` folds the profile's identifier in beside `--model`,
    # and `hold_model` reaches for the resident model only where the pair of
    # them named none. So a profile naming one needs nothing held, and saying
    # otherwise sends someone to load a model for a run that would load it.
    if request.identifier is not None:
        return (HELD_NOTHING, *unknown)

    # Under the line it is about, where a reading about what could leave puts
    # its own.
    return (
        HELD_NOTHING,
        *say_indented(
            REMEDY,
            "Load a model in the runtime, or name one under `model:` in the profile.",
        ),
        *unknown,
    )


def describe_a_discarded_window(answered: WhatTheRuntimeAnswered) -> tuple[str, ...]:
    """Say that offgrid stopped asking for a window, and how to make it ask.

    Deleting the file makes offgrid ask again, so this is where it is named:
    `doctor` is what a person runs when something is not what they asked for.
    The number the runtime served then is said as what it was — what it serves
    now is the `context_window` line above, and the two are read together.

    It takes what the runtime said rather than the whole reading, for the
    reason `describe_the_runtime` gives: a record offgrid keeps about a runtime
    is worth reading whatever the agent did.

    :param answered: What the runtime said.

    :return: A line for each window discarded and the way back under them, and
        nothing where none was.
    """
    if answered.unreadable is not None:
        return (say_in_columns("discarded", answered.unreadable),)

    if not answered.discarded:
        return ()

    return (
        *(
            say_in_columns(
                "discarded",
                f"{record.asked_for} was asked for on {record.dated} and "
                f"{record.served} served then, so offgrid is not asking again.",
            )
            for record in answered.discarded
        ),
        *say_indented(REMEDY, f"Delete {discarded_windows.DEFAULT_PATH} to ask again."),
    )
