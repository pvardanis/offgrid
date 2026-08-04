"""What offgrid remembers about a machine between runs.

Reading a machine is cheap; agreeing on which runtime and agent to use is a
decision. The profile holds the decision, so a later run is one word.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from offgrid.exceptions import ProfileError
from offgrid.machine import Machine

DEFAULT_PATH = Path.home() / ".offgrid" / "profile.yaml"


class Profile(BaseModel):
    """A machine, and what offgrid should run on it.

    :param host: Address the runtime listens on.
    :param runtime: Which runtime adapter to use.
    :param agent: Which agent adapter to use.
    :param chip: Marketing name of the SoC, as measured.
    :param memory_bytes: Unified memory, as measured.
    :param wired_limit_bytes: The GPU wired limit, or ``None`` at its default.
    :param model: The model to run unless one is named on the command line, or
        ``None`` to use whatever the runtime is already holding.

    A profile is hand-edited, so anything it says that offgrid cannot act on
    is refused rather than ignored: a name offgrid does not have is a mistake
    to report, not a preference to record.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    host: str
    runtime: Literal["lmstudio"] = "lmstudio"
    agent: Literal["claude-code"] = "claude-code"
    chip: str
    memory_bytes: int = Field(gt=0)
    wired_limit_bytes: int | None = Field(default=None, gt=0)
    model: str | None = None

    @classmethod
    def describing(
        cls, machine: Machine, *, host: str, model: str | None = None
    ) -> "Profile":
        """Build a profile from a measured machine.

        :param machine: The host offgrid is running on.
        :param host: Address the runtime listens on.
        :param model: The model to run by default, if one has been chosen.

        :return: A profile ready to save.
        """
        return cls(
            host=host,
            chip=machine.chip,
            memory_bytes=machine.memory_bytes,
            wired_limit_bytes=machine.wired_limit_bytes,
            model=model,
        )

    def remeasured(self, machine: Machine, *, host: str | None = None) -> "Profile":
        """Record the machine as it is now, keeping what was chosen by hand.

        :param machine: The host offgrid is running on.
        :param host: Address the runtime listens on, or ``None`` to keep the
            one already stored.

        :return: A profile ready to save.
        """
        return self.model_copy(
            update={
                "host": host or self.host,
                "chip": machine.chip,
                "memory_bytes": machine.memory_bytes,
                "wired_limit_bytes": machine.wired_limit_bytes,
            }
        )

    def machine(self) -> Machine:
        """Rebuild the machine this profile describes.

        :return: The machine as it was measured.
        """
        return Machine(
            chip=self.chip,
            memory_bytes=self.memory_bytes,
            wired_limit_bytes=self.wired_limit_bytes,
        )


def save(profile: Profile, path: Path = DEFAULT_PATH) -> None:
    """Write a profile where a later run will find it.

    :param profile: The profile to store.
    :param path: Where to write it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(profile.model_dump(), sort_keys=False))


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

    body = yaml.safe_load(path.read_text())
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
            f"{path} does not describe a machine offgrid can run on: {problems}. "
            "Fix it by hand, or run `offgrid setup` to write it again."
        ) from error
