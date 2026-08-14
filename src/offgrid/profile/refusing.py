"""What a section offgrid cannot read reads like.

A registry builds what its own names say and nothing else, so what it raises
is a parser's word for the fault. This is where it becomes a profile's.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from enum import Enum

from pydantic import ValidationError

from offgrid.exceptions import ProfileError


@contextmanager
def refuse_profile_section(
    said: dict, *, port: str, names: type[Enum]
) -> Iterator[None]:
    """Say what a section was refused for, as a profile error.

    The section it was in, the adapter it named, and what to do next — the
    same sentence every other profile error is. What the validator said is
    carried through as it wrote it, naming the fields it would not take.

    :param said: What the profile says about this port.
    :param port: Which section it is, as the file spells it.
    :param names: The adapters offgrid has for this port.

    :yield: To the registry building the section.

    :raise ProfileError: When the section is not one that adapter can read.
    """
    try:
        yield
    except KeyError as error:
        raise ProfileError(
            f"The `{port}` section of the profile names no adapter. Say which "
            f"one with `name:` — offgrid has {_get_implemented_adapters(names)}."
        ) from error
    except ValidationError as error:
        raise ProfileError(
            f"{_get_adapter_name(said)} cannot read the `{port}` section of "
            f"the profile:\n\n{error}\n\n"
            "Take it out of the file, or spell it the way that adapter does."
        ) from error
    except ValueError as error:
        raise ProfileError(
            f"The `{port}` section names {said.get('name')}, which offgrid has "
            f"no adapter for. It has {_get_implemented_adapters(names)}."
        ) from error
    except TypeError as error:
        raise ProfileError(
            f"The `{port}` section of the profile names something offgrid "
            f"settles itself: {error}. Take it out of the file."
        ) from error


def _get_adapter_name(said: dict) -> str:
    """Say which adapter a section asked for, as the file spells it.

    :param said: What the profile says about this port.

    :return: The adapter's name.
    """
    return str(said["name"])


def _get_implemented_adapters(names: type[Enum]) -> str:
    """List the adapters offgrid has for one port.

    :param names: The adapters offgrid has for this port.

    :return: Their names, as a profile spells them.
    """
    return ", ".join(str(one.value) for one in names)
