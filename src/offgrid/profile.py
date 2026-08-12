"""What offgrid remembers between runs.

Reading a machine is cheap; agreeing on which runtime and agent to use is a
decision. The profile holds the decision, so a later run is one word.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from offgrid.agent import AgentName
from offgrid.exceptions import ProfileError
from offgrid.runtime import RuntimeName

DEFAULT_PATH = Path.home() / ".offgrid" / "profile.yaml"


class Profile(BaseModel):
    """How to reach the runtime, and what offgrid should run against it.

    :param host: Address the runtime listens on.
    :param runtime: Which runtime adapter to use.
    :param agent: Which agent adapter to use.
    :param model: The model to run unless one is named on the command line, or
        ``None`` to use whatever the runtime is already holding.

    Nothing measured is kept here. The GPU limit moves — a runtime may raise
    it as it starts — so it is read where it is used rather than recorded.

    A profile is hand-edited, so anything it says that offgrid cannot act on
    is refused rather than ignored: a name offgrid does not have is a mistake
    to report, not a preference to record.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    host: str
    runtime: RuntimeName = RuntimeName.LMSTUDIO
    agent: AgentName = AgentName.CLAUDE_CODE
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


def load(path: Path = DEFAULT_PATH) -> Profile:
    """Read the stored profile.

    :param path: Where to read it from.

    :return: The stored profile.

    :raise ProfileError: When it is absent, unreadable, or incomplete. Each
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

    try:
        return Profile(**body)
    except ValidationError as error:
        problems = ", ".join(
            f"{problem['loc'][0] if problem['loc'] else 'the file'} "
            f"({problem['msg'].lower()})"
            for problem in error.errors()
        )
        raise ProfileError(
            f"{path} does not describe a run offgrid can make: {problems}. "
            "Fix it by hand, or run `offgrid setup` to write it again."
        ) from error
