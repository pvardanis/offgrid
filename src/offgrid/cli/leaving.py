"""How what a run could send off this machine reads in the report."""

from offgrid.domain.running.leaving import Reading, Status


def describe_what_could_leave(readings: tuple[Reading, ...]) -> tuple[str, ...]:
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
            said = (*said, f"          {reading.detail} {reading.remedy}".rstrip())

    return said
