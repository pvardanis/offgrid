"""Adapters for the servers that hold models in memory.

The registry is the one place a name becomes an adapter. `create_runtime_config`
turns what a profile says into what one adapter reads, and `connect_runtime`
opens a connection from that. Nothing else is exported beside them:
`import-linter` reads import statements as written, so a re-exported `LMStudio`
would be indistinguishable from the import the command line legitimately makes
— and the rule that only a registry may import a concrete adapter would stop
being checkable.

The two mappings are keyed alike and go together: one says what a name is
built from, the other what it is reached with.
"""

from offgrid.domain.runtime import Connect, Runtime, RuntimeConfig, RuntimeName
from offgrid.runtimes import lmstudio

RUNTIMES: dict[RuntimeName, Connect] = {RuntimeName.LMSTUDIO: lmstudio.connect}

RUNTIME_CONFIGS: dict[RuntimeName, type[RuntimeConfig]] = {
    RuntimeName.LMSTUDIO: lmstudio.LMStudioConfig
}


def create_runtime_config(runtime_dict: dict) -> RuntimeConfig:
    """Build what a profile's runtime section says, as its adapter reads it.

    What it says goes to the config unread: the name picks the class, and the
    class says which of the rest it accepts.

    :param runtime_dict: What the profile says about the runtime.

    :return: What that adapter is built from.

    :raise KeyError: When the section names no adapter at all.
    :raise ValueError: When the name is not one offgrid has an adapter for.
    :raise ValidationError: When the section says something that adapter
        cannot read. `profile.refusing` is what turns either into a sentence.
    """
    name = RuntimeName(runtime_dict["name"])
    kwargs = {key: value for key, value in runtime_dict.items() if key != "name"}

    return RUNTIME_CONFIGS[name](**kwargs)


def connect_runtime(config: RuntimeConfig) -> Runtime:
    """Reach the runtime the config is for, where it says it listens.

    Looked up by the config's own name, so a config cannot reach an adapter
    that would misread it.

    :param config: What the profile settled for the runtime.

    :return: A connection to it.
    """
    return RUNTIMES[config.name](config)
