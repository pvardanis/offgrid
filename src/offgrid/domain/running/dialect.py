"""The API shapes a runtime serves and the one an agent expects."""

from enum import Enum

from offgrid.shared.exceptions import DialectMismatchError


class Dialect(Enum):
    """An HTTP API shape for chat completions.

    A runtime serves a set of them; an agent speaks one. Where the one the
    agent speaks is not among them a translating proxy is needed, and offgrid
    says so rather than bundling one.
    """

    ANTHROPIC = "anthropic"
    OPENAI = "openai"


def require_compatible(served: frozenset[Dialect], expected: Dialect) -> None:
    """Refuse a runtime and an agent that cannot talk to each other.

    A membership test: a runtime serving several shapes pairs with an agent
    speaking any one of them.

    :param served: Every dialect the runtime serves.
    :param expected: The dialect the agent expects.

    :raise DialectMismatchError: When the runtime serves nothing the agent
        speaks.
    """
    if expected in served:
        return

    raise DialectMismatchError(
        f"The runtime serves {_name_what_is_served(served)} and the agent "
        f"expects {expected.value}. Put a translating proxy between them, or "
        f"pick a runtime that serves {expected.value}.",
        served=served,
        expected=expected,
    )


def _name_what_is_served(served: frozenset[Dialect]) -> str:
    """Say every dialect a runtime serves, so a reader can see which end to change.

    In a settled order, so that two runs of the same refusal read alike: a
    message built from a set's own order names them differently between calls
    with nothing changed.

    :param served: Every dialect the runtime serves.

    :return: What to put after "the runtime serves".
    """
    names = sorted(dialect.value for dialect in served)

    if not names:
        return "no dialect at all"

    if len(names) == 1:
        return f"the {names[0]} API"

    return f"the {' and '.join(names)} APIs"
