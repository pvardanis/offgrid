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

from pydantic import ValidationError

from offgrid.exceptions import ProfileError
from offgrid.profile import describe_problems
from offgrid.runtime import Connect, Runtime, RuntimeConfig, RuntimeName
from offgrid.runtimes import lmstudio

RUNTIMES: dict[RuntimeName, Connect] = {RuntimeName.LMSTUDIO: lmstudio.connect}

RUNTIME_CONFIGS: dict[RuntimeName, type[RuntimeConfig]] = {
    RuntimeName.LMSTUDIO: lmstudio.LMStudioConfig
}


def create_runtime_config(said: dict) -> RuntimeConfig:
    """Read a profile's runtime section as the adapter it names reads it.

    :param said: What the profile says about the runtime.

    :return: What that adapter is built from.

    :raise ProfileError: When the name is not one offgrid has an adapter for,
        or the section says something that adapter cannot read.
    """
    written = {key: value for key, value in said.items() if key != "name"}

    try:
        name = RuntimeName(said.get("name", RuntimeName.LMSTUDIO.value))
    except ValueError as error:
        raise ProfileError(
            f"The `runtime` section names {said['name']}, which offgrid has no "
            f"adapter for. It has {', '.join(one.value for one in RuntimeName)}."
        ) from error

    try:
        return RUNTIME_CONFIGS[name](**written)
    except ValidationError as error:
        raise ProfileError(
            f"{name.value} cannot read the `runtime` section of the profile: "
            f"{describe_problems(error)}. Take it out of the file, or spell it "
            "the way that adapter does."
        ) from error


def connect_runtime(config: RuntimeConfig) -> Runtime:
    """Reach the runtime the config is for, where it says it listens.

    Looked up by the config's own name, so a config cannot reach an adapter
    that would misread it.

    :param config: What the profile settled for the runtime.

    :return: A connection to it.
    """
    return RUNTIMES[config.name](config)
