"""Adapters for the servers that hold models in memory.

The registry is the one place a name becomes an adapter, and `connect_runtime`
is how a caller asks for that: what a profile names, bound to the address it
listens on. Nothing else is exported beside them: `import-linter` reads import
statements as written, so a re-exported `LMStudio` would be indistinguishable
from the import the command line legitimately makes — and the rule that only a
registry may import a concrete adapter would stop being checkable.
"""

from offgrid.profile import Profile
from offgrid.runtime import Connect, Runtime, RuntimeName
from offgrid.runtimes import lmstudio

RUNTIMES: dict[RuntimeName, Connect] = {RuntimeName.LMSTUDIO: lmstudio.connect}


def connect_runtime(profile: Profile) -> Runtime:
    """Reach the runtime the profile names, where the profile says it listens.

    :param profile: What the runtime is called, and where it listens.

    :return: A connection to it.
    """
    return RUNTIMES[profile.runtime](profile.host)
