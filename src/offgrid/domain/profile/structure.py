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

# A name to show the key with where the file carries nothing usable, and not
# a model offgrid picks: which one to run stays a manual choice.
EXAMPLE_MODEL = "qwen/qwen3.6-35b-a3b"


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

    :raise ProfileError: When `model` holds anything other than a section. A
        `model` key with nothing under it passes: it is a profile that names no
        model, and a run against whatever the runtime is already holding.
    """
    named = body.get("model")

    if named is None or isinstance(named, dict):
        return

    raise ProfileError(
        f"`model` in {path} is not a section, and a model is one: it carries "
        f"what to run and the window to run it at. Write it as:\n\n"
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

    A name is echoed rather than invented, so the fix is the section copied
    over the line it replaces. Anything that could not be a name — nothing at
    all, a number, a list — is answered with an example instead, since a
    section copied out of the message has to be one that loads. The window is
    shown at a number to read as an example, the key being the whole reason
    the section exists.

    :param named: What the file said under `model`.

    :return: A section to copy.
    """
    identifier = named if isinstance(named, str) and named else EXAMPLE_MODEL

    return yaml.safe_dump(
        {"model": {"identifier": identifier, "context_window": EXAMPLE_WINDOW}},
        sort_keys=False,
    ).strip()
