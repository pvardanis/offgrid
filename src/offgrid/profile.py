"""What offgrid remembers between runs.

Reading a machine is cheap; agreeing on which runtime and agent to use is a
decision. The profile holds the decision, so a later run is one word.

Reading the file and building a profile out of it are two calls, because the
sections belong to adapters and this module may not name one. Whoever has the
registries reads the file, asks each registry for its own section, and hands
both back here.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from offgrid.agent import AgentConfig, AgentName
from offgrid.exceptions import ProfileError
from offgrid.home import OFFGRID_HOME
from offgrid.runtime import RuntimeConfig, RuntimeName

DEFAULT_PATH = OFFGRID_HOME / "profile.yaml"

# An address to show a shape with, rather than one to reach anything at.
EXAMPLE_HOST = "127.0.0.1:1234"


class Profile(BaseModel):
    """How to reach the runtime, and what offgrid should run against it.

    One section per port, each naming its adapter and carrying whatever else
    that adapter reads. A section is where an adapter's own settings go, and
    where the file says which part of the system a setting belongs to.

    :param runtime: The runtime adapter to use, and where it listens.
    :param agent: The agent adapter to use.
    :param model: The model to run unless one is named on the command line, or
        ``None`` to use whatever the runtime is already holding. It belongs to
        neither adapter: a run discovers it, and ``--model`` beats it.

    Nothing measured is kept here. The GPU limit moves — a runtime may raise
    it as it starts — so it is read where it is used rather than recorded.

    A profile is hand-edited, so anything it says that offgrid cannot act on
    is refused rather than ignored: a name offgrid does not have is a mistake
    to report, not a preference to record.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime: RuntimeConfig
    agent: AgentConfig
    model: str | None = None


def save(profile: Profile, path: Path = DEFAULT_PATH) -> None:
    """Write a profile where a later run will find it.

    :param profile: The profile to store.
    :param path: Where to write it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Dumped as what YAML can carry: a plain dump answers with the enum member
    # itself, which `safe_dump` refuses with `cannot represent an object`.
    written = profile.model_dump(mode="json")

    path.write_text(yaml.safe_dump(written, sort_keys=False))


def load_yaml(path: Path = DEFAULT_PATH) -> dict:
    """Read the stored profile as the mapping it holds.

    What the sections mean is an adapter's business, so this reads no further
    than the shape: a file that is there, parses, and holds a mapping.

    :param path: Where to read it from.

    :return: What the file says, unread.

    :raise ProfileError: When it is absent, unreadable, or not a mapping. Each
        case says which, because a profile is hand-editable and a typo in it
        should not read as a machine that has changed.
    """
    if not path.exists():
        raise ProfileError(f"No profile at {path}. Run `offgrid setup` to make one.")

    try:
        body = yaml.safe_load(path.read_text())
    except yaml.YAMLError as error:
        raise ProfileError(
            f"{path} is not readable as YAML: {error}. Fix it by hand, or run "
            "`offgrid setup` to write it again."
        ) from error

    if not isinstance(body, dict):
        raise ProfileError(
            f"{path} is not a profile: it holds {type(body).__name__}, not a mapping."
        )

    _refuse_a_flat_profile(body, path)

    return body


def create_profile(
    body: dict, *, runtime: RuntimeConfig, agent: AgentConfig
) -> Profile:
    """Build a profile from a file and the configs its sections named.

    The body is passed whole with its two sections replaced, so a key that
    belongs to no section is still refused here rather than quietly ignored.

    :param body: What the file said.
    :param runtime: What the runtime section named, as its adapter reads it.
    :param agent: What the agent section named, as its adapter reads it.

    :return: What a run is made from.

    :raise ProfileError: When what is left over is not a profile.
    """
    rest = {
        key: value for key, value in body.items() if key not in ("runtime", "agent")
    }

    try:
        return Profile(runtime=runtime, agent=agent, **rest)
    except ValidationError as error:
        raise ProfileError(
            f"The profile does not describe a run offgrid can make: "
            f"{describe_problems(error)}. Fix it by hand, or run `offgrid "
            "setup` to write it again."
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


def _refuse_a_flat_profile(body: dict, path: Path) -> None:
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
            f"`host` belongs to the runtime. Write it as:\n\n{_example()}"
        )


def _example() -> str:
    """Write out a whole profile, in the shape offgrid reads.

    Spelled from the two enums, which are the domain's own vocabulary, so it
    stays true without this module naming an adapter package.

    :return: A profile to copy.
    """
    return yaml.safe_dump(
        {
            "runtime": {"name": RuntimeName.LMSTUDIO.value, "host": EXAMPLE_HOST},
            "agent": {"name": AgentName.CLAUDE_CODE.value},
        },
        sort_keys=False,
    ).strip()
