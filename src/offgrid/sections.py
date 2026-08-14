"""One section of the profile, read as the adapter it names declares it.

A section is permissive where the profile holds it, because it belongs to
whichever adapter its name picks and the profile cannot know what that one
reads. This is where that stops, and where an adapter handed a config built
for another says so.
"""

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ValidationError

from offgrid.agent import AgentConfig
from offgrid.exceptions import ProfileError
from offgrid.runtime import RuntimeConfig

type Port = Literal["agent", "runtime"]


def read_section[ConfigT: BaseModel](
    section: AgentConfig | RuntimeConfig,
    into: type[ConfigT],
    *,
    port: Port,
    settled: Mapping[str, object] | None = None,
) -> ConfigT:
    """Read one section of the profile as the settings an adapter declares.

    The adapter's own config names what it accepts and forbids the rest, so a
    key it does not read is reported rather than dropped.

    The remedy is by hand, and only by hand: `offgrid setup` keeps what it
    finds, so it would write the offending key straight back.

    :param section: What the profile says about this port.
    :param into: The config the adapter it names is built from.
    :param port: Which section it is, as the file spells it.
    :param settled: What offgrid supplies rather than reads, which the section
        may therefore not name itself.

    :return: The section as that adapter's config.

    :raise ProfileError: When the section names a key offgrid settles itself,
        or one the adapter does not read.
    """
    written = section.model_dump(mode="json")
    supplied = dict(settled or {})

    overreach = sorted(set(written) & set(supplied))
    if overreach:
        raise ProfileError(
            f"The `{port}` section of the profile names {', '.join(overreach)}, "
            "which offgrid settles itself. Take it out of the file."
        )

    try:
        return into.model_validate(written | supplied)
    except ValidationError as error:
        raise ProfileError(
            f"{section.name.value} cannot read the `{port}` section of the "
            f"profile: {describe_problems(error)}. Take it out of the file, or "
            "spell it the way that adapter does."
        ) from error


def as_declared[ConfigT: BaseModel](
    config: BaseModel,
    into: type[ConfigT],
    *,
    adapter: str,
    registry: str,
) -> ConfigT:
    """Read a config an adapter was handed as the one it declared.

    A registry maps a name to a config and to a factory in two places, and
    both are typed on the base so that either row can hold any adapter's. This
    is what stops a config reaching a factory that would misread it.

    :param config: What the registry handed over.
    :param into: The config this adapter declared.
    :param adapter: What this adapter is called in a profile.
    :param registry: Where the two rows that disagree are written.

    :return: The same config, as the type the adapter reads.

    :raise TypeError: When it was built for another adapter.
    """
    if not isinstance(config, into):
        raise TypeError(
            f"{adapter} was handed {type(config).__name__}, which is not its "
            f"own config. In {registry}, the name is bound to one adapter's "
            "config and another adapter's factory."
        )

    return config


def describe_problems(error: ValidationError) -> str:
    """Name what a validator refused, field by field.

    :param error: What the validator raised.

    :return: The fields and why each was refused, as one phrase.
    """
    return ", ".join(
        f"{'.'.join(str(part) for part in problem['loc']) or 'the file'} "
        f"({problem['msg'].lower()})"
        for problem in error.errors()
    )
