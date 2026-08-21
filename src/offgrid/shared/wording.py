"""The words offgrid uses for what somebody else did or did not state.

A runtime and a published list are both free to answer nothing for a number,
and every command that prints one owes the same word for it. Here rather than
beside the output channel, because the domain prints these too and has no
business importing what configures logging.
"""


def describe_what_was_stated(value: int | str | None) -> str:
    """Say what was stated, or that nothing was.

    Tested against ``None`` rather than for being falsy: a `Model` and a
    `Listing` are parsed from what somebody else answered and refuse nothing,
    so a zero that arrived is a number that was stated. Only the request a
    person writes refuses one, which is what lets `settle_what_to_run` read
    falsiness.

    :param value: What was stated, or ``None`` where nothing was.

    :return: What to print for it.
    """
    return "unstated" if value is None else str(value)
