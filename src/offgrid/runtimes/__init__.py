"""Adapters for the servers that hold models in memory.

The registry is the one place a name becomes an adapter. `create_runtime_config`
turns what a profile says into what one adapter reads, and `connect_runtime`
opens a connection from that. Nothing else is exported beside them:
`import-linter` reads import statements as written, so a re-exported `LMStudio`
would be indistinguishable from the import the command line legitimately makes
— and the rule that only a registry may import a concrete adapter would stop
being checkable.

The three mappings are keyed alike and go together: one says what a name is
built from, one what it is reached with, and one what it says about having a
model downloaded into it. A name missing from any of them is an adapter half
registered, which `tests/test_architecture.py` refuses.

The third takes no connection, because how a model is downloaded is a fact
about a runtime rather than about a connection to one: `recommend` names
models off a published list without asking anything on this machine, and
opening a connection to answer would be ceremony. Why it sits here rather than
on the `Runtime` port is in `docs/decisions.md`.
"""

from collections.abc import Callable

from offgrid.domain.running.runtime import Connect, Runtime, RuntimeConfig, RuntimeName
from offgrid.runtimes import lmstudio

DescribeDownload = Callable[[str], str]
"""How a runtime says one of its models is downloaded, given the model's name.

The answer names that model, and arrives in lines no wider than
`shared.wording.LINE_WIDTH` — nothing reflows it, since a command in it has to
survive being copied. `tests/test_runtime_downloading.py` holds every adapter
to both.
"""

RUNTIMES: dict[RuntimeName, Connect] = {RuntimeName.LMSTUDIO: lmstudio.connect}

RUNTIME_CONFIGS: dict[RuntimeName, type[RuntimeConfig]] = {
    RuntimeName.LMSTUDIO: lmstudio.LMStudioConfig
}

DOWNLOAD_INSTRUCTIONS: dict[RuntimeName, DescribeDownload] = {
    RuntimeName.LMSTUDIO: lmstudio.describe_download
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


def describe_download(runtime_name: RuntimeName, model: str) -> str:
    """Say how a model is downloaded into the runtime a profile names.

    Nothing is reached and no connection is opened: what comes back is the
    adapter's own words about its application.

    :param runtime_name: The runtime it would be downloaded into.
    :param model: The model it is about, spelt as a published list spells it.

    :return: What to do to have that model downloaded.
    """
    return DOWNLOAD_INSTRUCTIONS[runtime_name](model)
