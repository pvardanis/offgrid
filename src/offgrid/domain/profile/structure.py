"""Whether a profile is built the way offgrid reads one.

The shape, before anything asks what it says. A profile written flat is the one
offgrid read before it carried a section per adapter, and a model named on its
own key is the one it read before a window could be written down. Each is
refused rather than migrated.

Its own module because it has an end: once nobody has a profile in either older
shape left, this file goes and nothing else moves.
"""

from pathlib import Path

from offgrid.domain.profile.keeping import dump_yaml
from offgrid.domain.running.agent import AgentName
from offgrid.domain.running.runtime import RuntimeName
from offgrid.shared.exceptions import ProfileError

# An address to show a shape with, rather than one to reach anything at.
EXAMPLE_HOST = "127.0.0.1:1234"

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
        f"`model` in {path} {_say_what_it_holds(named)}, and a model is a "
        f"section: it carries what to run and the window to run it at. Write "
        f"it as:\n\n{_get_model_example(named)}\n\n"
        "Add `context_window:` beside it to hold the model at a window of "
        "your own. Left out, the runtime serves whatever it last remembered, "
        "which is what this profile asked for until now."
    )


def _get_example() -> str:
    """Write out a whole profile, in the shape offgrid reads.

    Spelled from the two enums, which are the domain's own vocabulary, so it
    stays true without this module naming an adapter package. It is also the
    whole of a minimal profile: only `model` may be left out.

    :return: A profile to copy.
    """
    return dump_yaml(
        {
            "runtime": {"name": RuntimeName.LMSTUDIO.value, "host": EXAMPLE_HOST},
            "agent": {"name": AgentName.CLAUDE_CODE.value},
        }
    ).strip()


def _say_what_it_holds(named: object) -> str:
    """Say what the `model` key was found holding, in a reader's words.

    Named rather than left out, because the refusal is about one key and a
    reader who cannot see which part of it offends has to guess.

    :param named: What the file said under `model`.

    :return: A phrase to follow the key with.
    """
    if isinstance(named, str):
        return "holds a name" if named else "holds nothing"

    return f"holds {'a list' if isinstance(named, list) else 'a number'}"


def _get_model_example(named: object) -> str:
    """Write out a model section, around the name a profile already carries.

    A name is echoed rather than invented, so the fix is the section copied
    over the line it replaces. Anything that could not be a name — an empty
    string, a number, a list — is answered with an example instead, since a
    section copied out of the message has to be one that loads.

    The window is left out of it. The file being refused asked for whichever
    window the runtime remembered, and a section that arrives carrying a
    number would change that for anyone who copied what they were told to.

    :param named: What the file said under `model`.

    :return: A section to copy.
    """
    identifier = named if isinstance(named, str) and named else EXAMPLE_MODEL

    return dump_yaml({"model": {"identifier": identifier}}).strip()
