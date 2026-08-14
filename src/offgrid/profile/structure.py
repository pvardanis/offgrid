"""Whether a profile is built the way offgrid reads one.

The shape, before anything asks what it says: a profile written flat is the
one offgrid read before it carried a section per adapter, and it is refused
rather than migrated.

Its own module because it has an end: once nobody has a flat profile left,
this file goes and nothing else moves.
"""

from pathlib import Path

import yaml

from offgrid.agent import AgentName
from offgrid.exceptions import ProfileError
from offgrid.runtime import RuntimeName

# An address to show a shape with, rather than one to reach anything at.
EXAMPLE_HOST = "127.0.0.1:1234"


def refuse_a_flat_profile(body: dict, path: Path) -> None:
    """Say that a profile written flat has to be nested, and how.

    The whole shape, because a reader given the name of one key that does not
    fit has to guess at the rest of the file.

    :param body: What the file holds.
    :param path: Where it was read from.

    :raise ProfileError: When the file names a port without a section.
    """
    flat = "host" in body or any(
        port in body and not isinstance(body[port], dict)
        for port in ("runtime", "agent")
    )

    if flat:
        raise ProfileError(
            f"{path} is flat, and a profile carries a section per adapter. "
            f"`host` belongs to the runtime. Write it as:\n\n{_get_example()}"
        )


def _get_example() -> str:
    """Write out a whole profile, in the shape offgrid reads.

    Spelled from the two enums, which are the domain's own vocabulary, so it
    stays true without this module naming an adapter package. It is also the
    whole of a minimal profile: only `model` may be left out.

    :return: A profile to copy.
    """
    return yaml.safe_dump(
        {
            "runtime": {"name": RuntimeName.LMSTUDIO.value, "host": EXAMPLE_HOST},
            "agent": {"name": AgentName.CLAUDE_CODE.value},
        },
        sort_keys=False,
    ).strip()
