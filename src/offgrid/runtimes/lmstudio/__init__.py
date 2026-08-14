"""LM Studio, which serves Anthropic's message API alongside OpenAI's.

`read_config` and `connect` are the whole of what the registry asks for: one
turns the profile's runtime section into what LM Studio reads, the other opens
a connection from it. What that answers with is in `lmstudio.py`, and what it
reaches for is beside it.
"""

from offgrid.runtime import Runtime, RuntimeConfig
from offgrid.runtimes.lmstudio.binding import LMStudioConfig, read_config
from offgrid.runtimes.lmstudio.lmstudio import LMStudio

__all__ = ["connect", "read_config"]


def connect(config: RuntimeConfig) -> Runtime:
    """Bind the address LM Studio listens on.

    :param config: What the profile settled for this runtime.

    :return: A connection offgrid can ask to hold a model.

    :raise TypeError: When the config was built for another runtime, which is
        a registry binding one name to two adapters.
    """
    if not isinstance(config, LMStudioConfig):
        raise TypeError(
            f"lmstudio was handed {type(config).__name__}, which is not its "
            "own config. In runtimes/__init__.py, the name is bound to one "
            "adapter's config and another adapter's factory."
        )

    return LMStudio(host=config.host)
