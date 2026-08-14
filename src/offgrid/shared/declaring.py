"""What an adapter declares, and reading a config as the one it declared.

A registry binds a name to a config in one row and to a factory in another,
and the type system ties neither to the other: both rows are stated over the
port's base config, so either can hold any adapter's. This is where a config
that reached the wrong factory stops.
"""

from pydantic import BaseModel


def as_declared[ConfigT: BaseModel](
    config: BaseModel, declared: type[ConfigT]
) -> ConfigT:
    """Read a config an adapter was handed as the one it declared.

    It says class names rather than adapter names, because what it reports is
    a mis-wired registry rather than a mis-typed profile — nobody who reads it
    is holding the file, and the two rows that disagree are written in Python.

    :param config: What the registry handed over.
    :param declared: The config this adapter declared.

    :return: The same config, as the type the adapter reads.

    :raise TypeError: When it was built for another adapter.
    """
    if not isinstance(config, declared):
        raise TypeError(
            f"{declared.__name__} was expected and {type(config).__name__} "
            "handed over. A registry binds a name to a config and to a "
            "factory, and those two rows have come apart."
        )

    return config
