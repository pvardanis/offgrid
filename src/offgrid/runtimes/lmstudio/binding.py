"""What LM Studio is bound to before a run starts.

Where it listens is all of it. The type is here anyway, so that a key nobody
reads is refused rather than carried, and so that a setting LM Studio grows
later has somewhere to land.
"""

from pydantic import ConfigDict

from offgrid.runtime import RuntimeConfig, RuntimeName
from offgrid.sections import read_section


class LMStudioConfig(RuntimeConfig):
    """Everything LM Studio is reached with.

    :param name: Always ``lmstudio``.
    :param host: Address the runtime listens on, e.g. ``127.0.0.1:1234``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: RuntimeName = RuntimeName.LMSTUDIO


def read_config(section: RuntimeConfig) -> LMStudioConfig:
    """Read the profile's runtime section as LM Studio's own settings.

    :param section: What the profile says about the runtime.

    :return: What the adapter is built from.

    :raise ProfileError: When the section says something LM Studio cannot
        read.
    """
    return read_section(section, LMStudioConfig, port="runtime")
