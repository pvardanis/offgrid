"""What offgrid remembers between runs.

Reading a machine is cheap; agreeing on which runtime and agent to use is a
decision. The profile holds the decision, so a later run is one word.

Reading the file and building a profile out of it are two calls, because the
sections belong to adapters and this module may not name one. Whoever has the
registries reads the file, asks each registry for its own section, and hands
both back here.
"""

from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializeAsAny,
    ValidationError,
    field_validator,
)

from offgrid.domain.profile.keeping import DuplicateKeyError, YAMLError, read_yaml
from offgrid.domain.profile.structure import (
    refuse_a_flat_profile,
    refuse_a_model_without_a_section,
)
from offgrid.domain.running.agent import AgentConfig, AgentName
from offgrid.domain.running.model import ModelRequest
from offgrid.domain.running.runtime import RuntimeConfig, RuntimeName
from offgrid.shared.exceptions import ProfileError
from offgrid.shared.home import OFFGRID_HOME

DEFAULT_PATH = OFFGRID_HOME / "profile.yaml"

THEMES = (
    "catppuccin-mocha",
    "catppuccin-latte",
    "nord",
    "gruvbox",
    "dracula",
    "tokyo-night",
    "monokai",
    "solarized-light",
)
"""The colour themes offgrid offers, in the order a key cycles them.

Names the screen applies as palettes, kept here rather than beside the screen
because it is a profile field's own vocabulary: what a hand-edited theme is
refused against, and what the picker cycles. Every one is a palette the screen
can actually draw, which a screen-side test holds this list to.
"""

DEFAULT_THEME = THEMES[0]
"""The theme a profile opens in where it names none, and what a fresh one saves.

Settled against the prototype (catppuccin-mocha), and first so that the cycle
a person walks starts where the screen already was.
"""


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
    :param theme: The colour theme the screen is drawn in, cycled live and kept
        between runs. Defaults where absent so a profile that names no theme
        still loads; a name offgrid does not have is refused.

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
    theme: str = DEFAULT_THEME

    @field_validator("theme")
    @classmethod
    def _theme_is_one_offgrid_has(cls, value: str) -> str:
        """Refuse a theme name offgrid cannot draw, naming the set that exists.

        The theme is hand-edited like the rest of the file, so a typo is a
        clear error rather than a silent fall back to the default — and the
        message names what is on offer, since a person cannot guess the set.

        :param value: The theme the file names.

        :return: The theme, unchanged, where it is one offgrid offers.

        :raise ValueError: When it is not, which pydantic turns into the
            refusal a reader sees.
        """
        if value not in THEMES:
            raise ValueError(
                f"theme {value!r} is not one offgrid has. "
                f"Pick one of: {', '.join(THEMES)}."
            )

        return value

    @property
    def runtime_name(self) -> RuntimeName:
        """The runtime this profile names.

        :return: The runtime's name, read off its config rather than down the
            chain that reaches it. Its ``.value`` is the string a person reads.
        """
        return self.runtime.name

    @property
    def agent_name(self) -> AgentName:
        """The agent this profile names.

        :return: The agent's name, read off its config rather than down the
            chain that reaches it. Its ``.value`` is the string a person reads.
        """
        return self.agent.name

    @property
    def runtime_host(self) -> str:
        """Where the runtime this profile names listens.

        :return: The address, read off the runtime's config rather than down
            the chain that reaches it.
        """
        return self.runtime.host


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
    except DuplicateKeyError as error:
        raise ProfileError(
            f"{path} says a key twice, at line {_get_line(error)}. A profile "
            "answers each key once, and offgrid will not pick which of the two "
            "you meant. Delete the line you do not want."
        ) from error
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


def _get_line(error: DuplicateKeyError) -> int:
    """Say which line of the file a key was found on a second time.

    :param error: What the reader refused.

    :return: The line, counted from one as an editor counts them.
    """
    return error.problem_mark.line + 1
