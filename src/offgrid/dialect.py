"""The API shape a runtime serves and an agent expects."""

from enum import Enum

from offgrid.exceptions import DialectMismatchError


class Dialect(Enum):
    """An HTTP API shape for chat completions.

    Runtimes serve one; agents speak one. Where they differ a translating
    proxy is needed, and offgrid says so rather than bundling one.
    """

    ANTHROPIC = "anthropic"
    OPENAI = "openai"


def require_compatible(served: Dialect, expected: Dialect) -> None:
    """Refuse a runtime and an agent that cannot talk to each other.

    :param served: The dialect the runtime serves.
    :param expected: The dialect the agent expects.

    :raise DialectMismatchError: When the two differ.
    """
    if served is expected:
        return

    raise DialectMismatchError(
        f"The runtime serves the {served.value} API and the agent expects "
        f"{expected.value}. Put a translating proxy between them, or pick a "
        f"runtime that serves {expected.value}.",
        served=served,
        expected=expected,
    )
