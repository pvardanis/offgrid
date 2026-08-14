"""LM Studio, which serves Anthropic's message API alongside OpenAI's.

`LMStudioConfig` and `connect` are the whole of what the registry asks for:
one says what a profile's runtime section may hold, the other opens a
connection from it. What that answers with is in `lmstudio.py`, and what it
reaches for is beside it.
"""

from offgrid.domain.runtime import Runtime, RuntimeConfig
from offgrid.runtimes.lmstudio.config import LMStudioConfig
from offgrid.runtimes.lmstudio.lmstudio import LMStudio
from offgrid.shared.declaring import as_declared


def connect(config: RuntimeConfig) -> Runtime:
    """Bind the address LM Studio listens on.

    :param config: What the profile settled for this runtime.

    :return: A connection offgrid can ask to hold a model.

    :raise TypeError: When the config was built for another runtime, which is
        a registry binding one name to two adapters.
    """
    return LMStudio(config=as_declared(config, LMStudioConfig))
