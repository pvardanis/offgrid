"""Whether a profile is built the way offgrid reads one.

The shape, before anything asks what it says. A profile written flat is the one
offgrid read before it carried a section per adapter, and a model named on its
own key is the one it read before a window could be written down. Each is
refused rather than migrated.

Its own module because it has an end: once nobody has a profile in either older
shape left, this file goes and nothing else moves.
"""

from pathlib import Path

import yaml

from offgrid.domain.running.agent import AgentName
from offgrid.domain.running.runtime import RuntimeName
from offgrid.shared.exceptions import ProfileError

# An address to show a shape with, rather than one to reach anything at.
EXAMPLE_HOST = "127.0.0.1:1234"

# A window to show the key with, and not a number offgrid recommends: what
# fits is the machine's answer, and `recommend` is where it is asked.
EXAMPLE_WINDOW = 32768


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


def refuse_a_model_without_a_section(body: dict, path: Path) -> None:
    """Say that a model named on its own key has to be a section, and how.

    `model: <a name>` is the shape every profile was in before a window could
    be written down, and there is nowhere in it for the window to go. The whole
    section is printed, carrying the name that was already there, because a
    reader given a key that no longer fits has to guess at what replaces it.

    :param body: What the file holds.
    :param path: Where it was read from.

    :raise ProfileError: When `model` names a model rather than holding a
        section. A `model` key with nothing under it is a profile that names no
        model, which is what `setup` writes and a run against whatever is
        resident.
    """
    named = body.get("model")

    if named is None or isinstance(named, dict):
        return

    raise ProfileError(
        f"{path} names a model on its own key, and a model is a section: it "
        f"carries what to run and the window to run it at. Write it as:\n\n"
        f"{_get_model_example(named)}\n\n"
        "Leave `context_window` out to keep whatever the runtime serves it at."
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


def _get_model_example(named: object) -> str:
    """Write out a model section, around the name a profile already carries.

    The name is echoed rather than invented, so the fix is the section copied
    over the line it replaces. The window is shown at a number a person can
    read as an example, since the key is the whole reason the section exists.

    :param named: What the file said under `model`.

    :return: A section to copy.
    """
    return yaml.safe_dump(
        {"model": {"identifier": named, "context_window": EXAMPLE_WINDOW}},
        sort_keys=False,
    ).strip()
