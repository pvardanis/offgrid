"""What offgrid remembers between runs.

Reading a machine is cheap; agreeing on which runtime and agent to use is a
decision. The profile holds the decision, so a later run is one word.

Reading the file and building a profile out of it are two calls, because the
sections belong to adapters and this module may not name one. Whoever has the
registries reads the file, asks each registry for its own section, and hands
both back here.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny, ValidationError

from offgrid.domain.profile.keeping import YAMLError, keep_hand_edits, read_yaml
from offgrid.domain.profile.structure import (
    refuse_a_flat_profile,
    refuse_a_model_without_a_section,
)
from offgrid.domain.running.agent import AgentConfig
from offgrid.domain.running.model import ModelRequest
from offgrid.domain.running.runtime import RuntimeConfig
from offgrid.shared.exceptions import ProfileError
from offgrid.shared.home import OFFGRID_HOME

DEFAULT_PATH = OFFGRID_HOME / "profile.yaml"


class Profile(BaseModel):
    """How to reach the runtime, and what offgrid should run against it.

    One section per port, each naming its adapter and carrying whatever else
    that adapter reads. A section is where an adapter's own settings go, and
    where the file says which part of the system a setting belongs to.

    Both sections are serialized as the object rather than the annotation.
    Pydantic writes a field through the type it is declared as, so a setting
    only one adapter declares would go out of the file without a word — and
    the next `setup` would write the profile back without it.

    :param runtime: The runtime adapter to use, and where it listens.
    :param agent: The agent adapter to use.
    :param model: What to run and the window to run it at, unless the command
        line says otherwise, or ``None`` to take whatever the runtime is
        already holding at whatever it is already serving it at. The section
        belongs to neither adapter: the agent sets the floor, the runtime
        honours the number and the model states the ceiling.

    Nothing measured is kept here. The GPU limit moves — a runtime may raise
    it as it starts — so it is read where it is used rather than recorded.

    A profile is hand-edited, so anything it says that offgrid cannot act on
    is refused rather than ignored: a name offgrid does not have is a mistake
    to report, not a preference to record.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime: SerializeAsAny[RuntimeConfig]
    agent: SerializeAsAny[AgentConfig]
    model: ModelRequest = Field(default_factory=ModelRequest)


def save_profile(profile: Profile, path: Path = DEFAULT_PATH) -> None:
    """Write a profile where a later run will find it.

    A file already saying what offgrid can act on is written over key by key
    rather than replaced, because it is hand-edited: the comments, the blank
    lines and the order somebody chose are theirs, and only the values are
    offgrid's to state. Any other file is written whole.

    :param profile: The profile to store.
    :param path: Where to write it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Dumped as what YAML can carry: a plain dump answers with the enum member
    # itself, which the writer refuses with `cannot represent an object`.
    written = profile.model_dump(mode="json")

    already = path.read_text() if path.exists() else ""

    path.write_text(keep_hand_edits(already, written))


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
        body = read_yaml(path.read_text())
    except YAMLError as error:
        raise ProfileError(
            f"{path} is not readable as YAML: {error}. Fix it by hand, or run "
            "`offgrid setup` to write it again."
        ) from error

    if not isinstance(body, dict):
        raise ProfileError(
            f"{path} is not a profile: it holds {type(body).__name__}, not a mapping."
        )

    refuse_a_flat_profile(body, path)
    refuse_a_model_without_a_section(body, path)

    return body


def create_profile(
    body: dict, *, runtime: RuntimeConfig, agent: AgentConfig
) -> Profile:
    """Build a profile from a file and the configs its sections named.

    The rest of the body is passed whole, so a key that belongs to no section
    is refused here rather than quietly ignored.

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
            f"The profile does not describe a run offgrid can make:\n\n{error}"
            "\n\nFix it by hand, or run `offgrid setup` to write it again."
        ) from error
