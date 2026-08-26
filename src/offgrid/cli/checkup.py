"""What a run can be told before it costs a load, and how it reads."""

from dataclasses import dataclass

from offgrid.domain.profile import Profile
from offgrid.domain.running import discarded_windows
from offgrid.domain.running.asking import describe_what_is_asked_for
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.discarded_windows import DiscardedWindow
from offgrid.domain.running.keeping import Conversations
from offgrid.domain.running.leaving import Reading, Status
from offgrid.domain.running.model import Model, ModelRequest
from offgrid.shared.wording import describe_what_was_stated

HELD_NOTHING = "model     nothing held"


@dataclass(frozen=True)
class Checkup:
    """Everything `doctor` read, including what it found nothing to read.

    Readings rather than the things that answered them: the agent port can
    write its own settings, and a value the report is built from has no call
    to carry the means of doing it.

    :param profile: What was written down.
    :param resident: The model the runtime is holding, or ``None`` where it
        holds none — which the rest of the report survives, because a runtime
        holding nothing still answered.
    :param could_leave: What the agent says about each way this run could
        reach off this machine, one reading each.
    :param kept: Where the agent keeps a conversation a run starts, and how to
        open one again — which nothing outside a run finds.
    :param dialect: What the agent speaks.
    :param served: Every dialect the runtime serves, which says whether an
        agent other than this one would pair with it.
    :param context_floor: The smallest window the agent can start in.
    :param discarded: Every window this runtime discarded for the model it is
        holding, and empty where it discarded none and where the records could
        not be read — which is itself a finding, carried in `unreadable`.
    :param unreadable: Why the records could not be read, where they could not.
        A stale file nobody has heard of is worth a line, not the whole report.
    """

    profile: Profile
    resident: Model | None
    could_leave: tuple[Reading, ...]
    kept: Conversations
    dialect: Dialect
    served: frozenset[Dialect]
    context_floor: int
    discarded: tuple[DiscardedWindow, ...]
    unreadable: str | None


def describe_what_was_read(checkup: Checkup) -> tuple[str, ...]:
    """Put the report into the lines it is read as.

    A value rather than a run of statements that each print, so what the
    report says is settled in one place and said in another.

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
        f"floor     {checkup.context_floor}",
        *_describe_what_could_leave(checkup.could_leave),
        *_describe_where_conversations_are_kept(checkup.kept),
    )

    return (*said, *_describe_a_discarded_window(checkup))


def _describe_what_could_leave(readings: tuple[Reading, ...]) -> tuple[str, ...]:
    """Say what each way off this machine is in, and how to close an open one.

    One line per reading, so the report says which of them it is telling
    somebody about, with what a run would refuse with under the line it is
    about — said here instead of after the load the command was run to save.

    `DENIED` alone says no more than the state, because that is the one answer
    with nothing behind it to check and nothing to act on: the lines beside it
    are what somebody came for. `NONE_OFFERED` says its detail, because a claim
    that an agent has no such thing is only worth what the evidence beside it
    is, and this report is where a person reads that evidence.

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

    On every run rather than where an installation is kept apart, because there
    is no second case: every agent offgrid runs is run out of a directory of
    offgrid's, so a branch with one arm would claim a kind of agent that does
    not exist.

    The way back goes under the directory, where a reading about what could
    leave puts its remedy: a directory on its own is what a person already had.

    :param kept: Where the agent keeps them, and how to open one again.

    :return: The lines to say, in the order they are read.
    """
    return (f"kept      {kept.kept_in}", f"          {kept.resumed_by}")


def _describe_the_model(model: Model | None, request: ModelRequest) -> tuple[str, ...]:
    """Say which model would answer, and at what, or that none would.

    A runtime holding nothing keeps its lines in the column, the two numbers
    marked `unknown` rather than left out: a number about a model that is not
    held is unknown, where `unstated` is what a held model states when the
    runtime says no number for it.

    :param model: The model the runtime is holding, or ``None`` for none.
    :param request: What the profile asks the next run for, which decides
        whether a runtime holding nothing needs a hand.

    :return: The model's lines, and what to do about a runtime holding
        nothing where the profile names none either.
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

    Deleting the file makes offgrid ask again, so this is where it is named:
    `doctor` is what a person runs when something is not what they asked for.
    The number the runtime served then is said as what it was — what it serves
    now is the `window` line above, and the two are read together.

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
