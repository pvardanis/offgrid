"""One section of the profile, read as the adapter it names declares it.

A section is permissive where the profile holds it, because it belongs to
whichever adapter its name picks and the profile cannot know what that one
reads. This is where that stops.
"""

from collections.abc import Mapping

from pydantic import BaseModel, ValidationError

from offgrid.exceptions import ProfileError


def read_section[ConfigT: BaseModel](
    section: BaseModel,
    into: type[ConfigT],
    *,
    port: str,
    settled: Mapping[str, object] | None = None,
) -> ConfigT:
    """Read one section of the profile as the settings an adapter declares.

    The adapter's own config names what it accepts and forbids the rest, so a
    key it does not read is reported rather than dropped.

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
            f"{written.get('name', port)} cannot read the `{port}` section of "
            f"the profile: {describe_problems(error)}. Fix it by hand, or run "
            "`offgrid setup` to write it again."
        ) from error


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
