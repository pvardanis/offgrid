"""What offgrid remembers between runs.

Reading a machine is cheap; agreeing on which runtime and agent to use is a
decision. The profile holds the decision, so a later run is one word.

Reading the file and building a profile out of it are two calls, because the
sections belong to adapters and this module may not name one. Whoever has the
registries reads the file, asks each registry for its own section, and hands
both back here.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from enum import Enum
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
            f"{_problems(error)}. Fix it by hand, or run `offgrid "
            "setup` to write it again."
        ) from error


@contextmanager
def refusing(said: dict, *, port: str, names: type[Enum]) -> Iterator[None]:
    """Say what a section was refused for, as a profile error.

    A registry builds what its own names say and nothing else, so what it
    raises is a parser's word for the fault rather than a reader's. This is
    where it becomes one: the section it was in, the adapter it named, and
    what to do next — the same sentence every other profile error is.

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
            f"one with `name:` — offgrid has {_offered(names)}."
        ) from error
    except ValueError as error:
        if isinstance(error, ValidationError):
            raise ProfileError(
                f"{_named(said)} cannot read the `{port}` section of "
                f"the profile: {_problems(error)}. Take it out of the file, or "
                "spell it the way that adapter does."
            ) from error

        raise ProfileError(
            f"The `{port}` section names {said.get('name')}, which offgrid has "
            f"no adapter for. It has {_offered(names)}."
        ) from error
    except TypeError as error:
        raise ProfileError(
            f"The `{port}` section of the profile names something offgrid "
            f"settles itself: {error}. Take it out of the file."
        ) from error


def _named(said: dict) -> str:
    """Say which adapter a section asked for, as the file spells it.

    :param said: What the profile says about this port.

    :return: The adapter's name.
    """
    return str(said["name"])


def _offered(names: type[Enum]) -> str:
    """List the adapters offgrid has for one port.

    :param names: The adapters offgrid has for this port.

    :return: Their names, as a profile spells them.
    """
    return ", ".join(str(one.value) for one in names)


def _problems(error: ValidationError) -> str:
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
