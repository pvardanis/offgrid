"""Adapters for the servers that hold models in memory.

The registry is the one place a name becomes an adapter, and `connect_runtime`
is how a caller asks for that: what a profile names, read as that adapter's own
settings and bound to them. Nothing else is exported beside them:
`import-linter` reads import statements as written, so a re-exported `LMStudio`
would be indistinguishable from the import the command line legitimately makes
— and the rule that only a registry may import a concrete adapter would stop
being checkable.

The two mappings are keyed alike and go together: one turns the profile's
runtime section into a config, the other turns that config into a connection.
A name in one and not the other is a mis-wiring the suite catches.
"""

from offgrid.profile import Profile
from offgrid.runtime import Connect, MakeRuntimeConfig, Runtime, RuntimeName
from offgrid.runtimes import lmstudio

RUNTIMES: dict[RuntimeName, Connect] = {RuntimeName.LMSTUDIO: lmstudio.connect}

RUNTIME_CONFIGS: dict[RuntimeName, MakeRuntimeConfig] = {
    RuntimeName.LMSTUDIO: lmstudio.read_config
}


def connect_runtime(profile: Profile) -> Runtime:
    """Reach the runtime the profile names, where the profile says it listens.

    :param profile: What the runtime is called, and where it listens.

    :return: A connection to it.

    :raise ProfileError: When the runtime section says something that adapter
        cannot read.
    """
    name = profile.runtime.name

    return RUNTIMES[name](RUNTIME_CONFIGS[name](profile.runtime))
