"""What a run can be told before it costs a load, and how it reads."""

from dataclasses import dataclass
from pathlib import Path

from offgrid.domain.profile import Profile
from offgrid.domain.running import discarded_windows
from offgrid.domain.running.agent import AgentName
from offgrid.domain.running.asking import describe_what_is_asked_for
from offgrid.domain.running.conversations import Conversations
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.discarded_windows import DiscardedWindow
from offgrid.domain.running.leaving import Reading, Status
from offgrid.domain.running.model import Model, ModelRequest
from offgrid.domain.running.presence import say_where_an_agent_comes_from
from offgrid.shared.wording import describe_what_was_stated

HELD_NOTHING = "model     nothing held"


@dataclass(frozen=True)
class Checkup:
    """Everything `doctor` read, including what it found nothing to read.

    :param profile: What was written down.
    :param resident: The model the runtime is holding, or ``None`` where it
        holds none — which the rest of the report survives, a runtime holding
        nothing having still answered.
    :param could_leave: What the agent says about each way this run could
        reach off this machine.
    :param kept: Where the agent keeps a conversation a run starts, and how to
        open one again.
    :param dialect: What the agent speaks.
    :param served: Every dialect the runtime serves, which says whether
        another agent would pair with it.
    :param context_floor: The smallest window the agent can start in.
    :param command: What starting the agent runs, which is what was looked up.
    :param found_at: Where the `PATH` a run inherits has that command, and
        ``None`` where it has not got it at all.
    :param discarded: Every window this runtime discarded for the model it is
        holding, and empty where it discarded none and where the records would
        not read — itself a finding, carried in `unreadable`.
    :param unreadable: Why the records would not read, where they would not. A
        stale file nobody has heard of is worth a line, not the whole report.
    """

    profile: Profile
    resident: Model | None
    could_leave: tuple[Reading, ...]
    kept: Conversations
    dialect: Dialect
    served: frozenset[Dialect]
    context_floor: int
    command: str
    found_at: Path | None
    discarded: tuple[DiscardedWindow, ...]
    unreadable: str | None


def describe_what_was_read(checkup: Checkup) -> tuple[str, ...]:
    """Put the report into the lines it is read as.

    :param checkup: What the profile, the runtime and the agent answered.

    :return: The lines to say, in the order they are read.
    """
    profile = checkup.profile

    said = (
        f"runtime   {profile.runtime.name.value} at {profile.runtime.host}, reachable",
        f"serving   {', '.join(sorted(d.value for d in checkup.served))}",
        *_describe_the_model(checkup.resident, profile.model),
        f"profile   {describe_what_is_asked_for(profile.model)}",
        f"agent     {profile.agent.name.value}, speaking {checkup.dialect.value}",
        *_describe_where_the_agent_is(checkup, profile.agent.name),
        f"floor     {checkup.context_floor}",
        *_describe_what_could_leave(checkup.could_leave),
        *_describe_where_conversations_are_kept(checkup.kept),
    )

    return (*said, *_describe_a_discarded_window(checkup))


def _describe_where_the_agent_is(checkup: Checkup, name: AgentName) -> tuple[str, ...]:
    """Say the command a run would start, and where the `PATH` has it.

    Said at all because the alternative is exit 127, after a model has been
    loaded and let go again. Where it comes from goes under the line it is
    about — a link and not a command, for the reason `presence.py` gives.

    :param checkup: What was read.
    :param name: The agent the profile names, which is what is not installed.

    :return: The command's line, and where to get it where it is not here.
    """
    if checkup.found_at is not None:
        return (f"command   {checkup.command}, at {checkup.found_at}",)

    return (
        f"command   {checkup.command}, not on PATH",
        f"          {say_where_an_agent_comes_from(name)}",
    )


def _describe_what_could_leave(readings: tuple[Reading, ...]) -> tuple[str, ...]:
    """Say what each way off this machine is in, and how to close an open one.

    One line per reading, so the report says which it is telling somebody
    about. `DENIED` says no more, having nothing behind it to check.

    :param readings: What the agent said about each way off this machine.

    :return: The lines to say, in the order the agent answered them.
    """
    said: tuple[str, ...] = ()

    for reading in readings:
        said = (*said, f"leaves    {reading.subject}: {reading.status}")

        if reading.status is not Status.DENIED:
            said = (*said, f"          {reading.said}")

    return said


def _describe_where_conversations_are_kept(kept: Conversations) -> tuple[str, ...]:
    """Say where a conversation this run starts lands, and the way back into it.

    The way back goes under the directory: one on its own is what a person had.

    :param kept: Where the agent keeps them, and how to open one again.

    :return: The lines to say, in the order they are read.
    """
    return (f"kept      {kept.kept_in}", f"          {kept.said}")


def _describe_the_model(model: Model | None, request: ModelRequest) -> tuple[str, ...]:
    """Say which model would answer, and at what, or that none would.

    A runtime holding nothing keeps its lines in the column, marked `unknown`
    rather than left out, where `unstated` is a held model's own silence.

    :param model: The model the runtime is holding, or ``None`` for none.
    :param request: What the profile asks the next run for, which decides
        whether a runtime holding nothing needs a hand.

    :return: The model's lines, and what to do about a runtime holding nothing
        where the profile names none either.
    """
    if model is not None:
        return (
            f"model     {model.identifier}",
            f"ceiling   {describe_what_was_stated(model.context_ceiling)}",
            f"window    {describe_what_was_stated(model.context_window)}",
        )

    unknown = ("ceiling   unknown", "window    unknown")

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
        "          Load a model in the runtime, or name one under `model:` "
        "in the profile.",
        *unknown,
    )


def _describe_a_discarded_window(checkup: Checkup) -> tuple[str, ...]:
    """Say that offgrid stopped asking for a window, and how to make it ask.

    Deleting the file makes offgrid ask again, so this is where it is named.

    :param checkup: What the profile, the runtime and the agent answered.

    :return: A line for each window discarded and the way back under them, and
        nothing where none was.
    """
    if checkup.unreadable is not None:
        return (f"discarded {checkup.unreadable}",)

    if not checkup.discarded:
        return ()

    return (
        *(
            f"discarded {record.asked_for} was asked for on {record.dated} "
            f"and {record.served} served then, so offgrid is not asking again."
            for record in checkup.discarded
        ),
        f"Delete {discarded_windows.DEFAULT_PATH} to ask again.",
    )
