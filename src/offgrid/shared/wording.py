"""The word offgrid uses for a number somebody else did not state.

A runtime and a published list are both free to answer nothing for a number,
and nothing is not zero: the types those are read into validate neither, so
falsiness reports a number that arrived as one that never came. Numbers only —
where a string is absent or empty, a reader is owed the same word for both,
and each place that prints one has its own.

Here rather than beside the output channel, so that the sizing domain, which
composes lines it does not say, need not reach the module that configures
logging.
"""


def describe_what_was_stated(value: int | None) -> str:
    """Say what number was stated, or that none was.

    :param value: The number stated, or ``None`` where none was.

    :return: The text to read it as.
    """
    return "unstated" if value is None else str(value)
