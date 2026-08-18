"""What docs/architecture.md and the import contracts claim, against the tree.

The map enumerates the modules by hand and goes stale the silent way: somebody
adds a module, or splits one, and it notices nothing. A map that has quietly
stopped describing the code is worse than none, because it is still read.

The contracts are stated over one name per layer, so a module cannot fall out
of them by being forgotten — but a whole package can, by landing outside every
layer. That module is outside the check rather than passing it, and nothing
else would say so.

One rule no contract can carry at all is that only a registry may import a
concrete adapter. `import-linter` reads import statements as written, and a
registry importing the adapter beside it is the same statement shape as anyone
else importing it, so the rule is a test here instead. It reads the imports
each file writes, so a name reached at runtime — `importlib.import_module`, or
walking to `offgrid.runtimes.lmstudio` as an attribute of the package — is out
of its sight. Both are deliberate work to write, which the rule is not there to
stop; what it catches is the import somebody adds without thinking.

This is a regression guard, not a slice: it passes the day it is written. It
was checked by taking a module out of the map, a package out of every layer, a
registry entry out of its dict, and by pointing a module at a concrete adapter
— and watching each fail.
"""

import ast
import tomllib
from pathlib import Path

import pytest
from pydantic import BaseModel

ROOT = Path(__file__).parent.parent
DOC = ROOT / "docs" / "architecture.md"
PYPROJECT = ROOT / "pyproject.toml"
SOURCE = ROOT / "src" / "offgrid"

# One name per layer, as the tree says it. A module belongs to the layer of the
# package above it, so these stay this length however many modules there are.
DOMAIN_CONTRACT = "The domain knows nothing about adapters"

# Held here rather than derived, so that calling a package shared is a decision
# someone makes rather than something a heuristic infers. Anything shared is
# reachable from every layer, which is a thing to be sure about.
ADAPTERS = {"offgrid.agents", "offgrid.leaderboards", "offgrid.runtimes"}
COMMAND_LINE = {"offgrid.cli", "offgrid.binding"}
SHARED = {"offgrid.shared"}


def _modules() -> set[str]:
    """Every module in the package, as import-linter names them."""
    return {
        "offgrid." + ".".join(path.relative_to(SOURCE).with_suffix("").parts)
        for path in SOURCE.rglob("*.py")
        if path.name != "__init__.py"
    }


def _packages() -> set[str]:
    """Every package in the tree, which `_modules` cannot see.

    A package's `__init__.py` holds imports like any other file, and the rule
    is stated over module names — so a package left out of the contract is one
    whose `__init__.py` may reach anywhere, unnoticed.
    """
    return {
        "offgrid." + ".".join(path.parent.relative_to(SOURCE).parts)
        for path in SOURCE.rglob("__init__.py")
        if path.parent != SOURCE
    }


def _named(path: Path) -> str:
    """A file in the tree, as an import statement names it.

    A package is named by its directory: the registry in `runtimes/__init__.py`
    is `offgrid.runtimes`, the name the rest of the tree legitimately imports.
    """
    parts = path.relative_to(SOURCE).with_suffix("").parts

    if parts[-1] == "__init__":
        parts = parts[:-1]

    return ".".join(("offgrid", *parts))


def _adapters() -> set[str]:
    """Every concrete adapter there is, as an import statement names it.

    Read from the tree rather than listed, so an adapter written after this is
    covered by existing rather than by somebody remembering to come back here.
    A directory counts whether or not it holds an `__init__.py`, since Python
    imports one either way and an adapter laid out without one would otherwise
    be outside the rule rather than passing it.
    """
    return {
        f"{package}.{adapter.stem}"
        for package in ADAPTERS
        for adapter in (SOURCE / package.rsplit(".", 1)[-1]).iterdir()
        if adapter.name != "__init__.py"
        and adapter.name != "__pycache__"
        and (adapter.suffix == ".py" or adapter.is_dir())
    }


def _reached_by(node: ast.ImportFrom, within: str) -> str:
    """Where a `from` import reaches, as an absolute name.

    A relative import names the same module as an absolute one and is only
    written differently, so it is resolved rather than skipped: `from
    .runtimes import lmstudio` in `cli.py` reaches the adapter exactly as far.

    :param node: The import to place.
    :param within: The package the file holding it belongs to.

    :return: The module the names are imported from.
    """
    if not node.level:
        return node.module or ""

    base = within.rsplit(".", node.level - 1)[0]

    return f"{base}.{node.module}" if node.module else base


def _imported(path: Path) -> set[str]:
    """Every module a file imports, as an import statement names it.

    A name imported from a package may itself be a module — `from
    offgrid.runtimes import lmstudio` reaches the adapter as surely as naming
    it in full — so both readings of a `from` are collected.
    """
    module = _named(path)
    within = module if path.name == "__init__.py" else module.rsplit(".", 1)[0]
    reached: set[str] = set()

    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            reached.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _reached_by(node, within)
            reached.add(base)
            reached.update(f"{base}.{alias.name}" for alias in node.names)

    return reached


def _is_within(module: str, package: str) -> bool:
    """Whether a name is a package or something underneath it."""
    return module == package or module.startswith(f"{package}.")


def _reaches_past_a_registry(module: str, reached: str, adapters: set[str]) -> bool:
    """Whether an import names a concrete adapter from outside it.

    The unit is the adapter package rather than the module, because an
    adapter's own files import each other: `lmstudio/lmstudio.py` reaches
    `lmstudio/catalogue.py` for the payload it reads. What is forbidden is
    reaching *into* an adapter from outside, which the registry beside it may
    do and nobody else — the command line included.

    :param module: The module the import is written in.
    :param reached: What that import names.
    :param adapters: Every concrete adapter in the tree.

    :return: Whether the import is one only a registry may make.
    """
    return any(
        _is_within(reached, adapter)
        and not _is_within(module, adapter)
        and module != adapter.rsplit(".", 1)[0]
        for adapter in adapters
    )


def _say_what_to_bind[Name](
    names: set[Name],
    bound: set[Name],
    *,
    enum: str,
    registry: str,
    module: str,
) -> str:
    """What to do about an enum and a registry naming different sets.

    :param names: Every name the enum holds.
    :param bound: Every name the registry has an entry for.
    :param enum: What the enum is called, to say it in the sentence.
    :param registry: What the registry is called.
    :param module: Where the registry lives, as a path to open.

    :return: The sentence naming what is adrift and what to do about it.
    """
    adrift = sorted(str(name) for name in names ^ bound)

    return (
        f"{adrift} is in one of {enum} and {registry} and not the other. Add "
        f"the entry to {registry} in {module}, or take the name out of {enum}."
    )


def _domain_in_the_contract() -> set[str]:
    """The modules the layer rule is stated over."""
    contracts = tomllib.loads(PYPROJECT.read_text())["tool"]["importlinter"][
        "contracts"
    ]
    stated = next(one for one in contracts if one["name"] == DOMAIN_CONTRACT)

    return set(stated["source_modules"])


def _is_covered(module: str, named: set[str]) -> bool:
    """Whether a module, or a package above it, is named as a layer.

    Both contracts are stated over packages and cover everything beneath one,
    so a module is placed by the first name above it that a layer claims.

    :param module: The module to place.
    :param named: Every name a layer is stated over.

    :return: Whether the layer rule reaches it.
    """
    parts = module.split(".")

    return any(".".join(parts[:depth]) in named for depth in range(1, len(parts) + 1))


def _below(base: type[BaseModel]) -> list[type[BaseModel]]:
    """Every model descending from one, however far down."""
    return [
        descendant
        for child in base.__subclasses__()
        for descendant in (child, *_below(child))
    ]


def test_the_doc_names_every_module_there_is():
    missing = sorted(
        module
        for module in _modules()
        if module.rsplit(".", 1)[-1] + ".py" not in DOC.read_text()
    )

    assert not missing, (
        f"docs/architecture.md does not mention {missing}. Add each to the map "
        "under the layer it belongs to."
    )


def test_every_module_is_covered_by_the_layer_rule():
    named = _domain_in_the_contract() | ADAPTERS | COMMAND_LINE | SHARED

    unclassified = sorted(
        module for module in _modules() | _packages() if not _is_covered(module, named)
    )

    assert not unclassified, (
        f"{unclassified} sits in no layer, so no import contract covers it. "
        "Move it under the layer it belongs to, or state a contract over it "
        "in pyproject.toml and name it here."
    )


def test_only_a_registry_imports_a_concrete_adapter():
    adapters = _adapters()

    assert adapters, "no adapter is in the tree, so this checks nothing"

    reaching = sorted(
        f"{_named(path)} imports {reached}"
        for path in SOURCE.rglob("*.py")
        for reached in _imported(path)
        if _reaches_past_a_registry(_named(path), reached, adapters)
    )

    assert not reaching, (
        f"{reaching} reaches into an adapter from outside it. Remove each "
        "import: a concrete adapter is named by the registry in its own "
        "package's __init__.py and nowhere else, the command line included. "
        "Ask that registry for one instead."
    )


def test_every_runtime_offgrid_names_has_an_adapter_bound_to_it():
    # Two places that cannot be one: an enum carrying its own factory would
    # be a domain type importing an adapter. A name with no entry raises a
    # KeyError at somebody's terminal, halfway through a run.
    from offgrid.domain.running.runtime import RuntimeName
    from offgrid.runtimes import RUNTIME_CONFIGS, RUNTIMES

    assert set(RUNTIMES) == set(RuntimeName), _say_what_to_bind(
        set(RuntimeName),
        set(RUNTIMES),
        enum="RuntimeName",
        registry="RUNTIMES",
        module="offgrid/runtimes/__init__.py",
    )
    assert set(RUNTIME_CONFIGS) == set(RuntimeName), _say_what_to_bind(
        set(RuntimeName),
        set(RUNTIME_CONFIGS),
        enum="RuntimeName",
        registry="RUNTIME_CONFIGS",
        module="offgrid/runtimes/__init__.py",
    )


def test_every_agent_offgrid_names_has_an_adapter_bound_to_it():
    from offgrid.agents import AGENT_CONFIGS, AGENTS
    from offgrid.domain.running.agent import AgentName

    assert set(AGENTS) == set(AgentName), _say_what_to_bind(
        set(AgentName),
        set(AGENTS),
        enum="AgentName",
        registry="AGENTS",
        module="offgrid/agents/__init__.py",
    )
    assert set(AGENT_CONFIGS) == set(AgentName), _say_what_to_bind(
        set(AgentName),
        set(AGENT_CONFIGS),
        enum="AgentName",
        registry="AGENT_CONFIGS",
        module="offgrid/agents/__init__.py",
    )


def test_offgrid_has_at_least_one_published_list_to_read():
    # Nothing names a leaderboard — no profile key, no argument — so the
    # registry is the whole statement of which lists there are. An empty one
    # sends every `recommend` down the fall back with nothing to say about
    # why, which is a long way from where the entry was dropped.
    from offgrid.leaderboards import LEADERBOARDS

    assert LEADERBOARDS, (
        "offgrid reads no published list at all. Add a Leaderboard to "
        "LEADERBOARDS in offgrid/leaderboards/__init__.py, pairing one "
        "module's fetch with the same module's parse."
    )


def test_every_config_an_adapter_declares_forbids_a_key_it_does_not_name():
    # A config declares what its adapter reads and refuses the rest, so that a
    # typo under a section is reported rather than dropped. The base says so
    # once and every adapter inherits it — a subclass that set `extra` back to
    # `allow` would accept junk in silence, which is the failure this whole
    # area exists to prevent.
    from offgrid.agents import AGENTS
    from offgrid.domain.running.agent import AgentConfig
    from offgrid.domain.running.runtime import RuntimeConfig
    from offgrid.runtimes import RUNTIMES

    # The registries are what import every adapter, and an adapter has to have
    # been imported for the config it declares to be a subclass yet.
    assert AGENTS and RUNTIMES

    declared = [
        config
        for config in (*_below(AgentConfig), *_below(RuntimeConfig))
        if config.__module__.startswith("offgrid.")
    ]
    permissive = sorted(
        config.__name__
        for config in declared
        if config.model_config.get("extra") != "forbid"
    )

    assert declared, "no adapter declares a config, so this checks nothing"
    assert not permissive, (
        f"{permissive} carries keys it does not name. Set "
        '`model_config = ConfigDict(extra="forbid", frozen=True)` on each.'
    )


def test_a_config_built_for_one_agent_cannot_reach_another_s_factory():
    # Both registry dicts are typed on the base config, so nothing stops a
    # name being bound to one adapter's config and another's factory. What
    # stops it reaching an adapter that would misread it is this refusal.
    from offgrid.agents.claude_code import prepare
    from tests.doubles import StandInAgentConfig

    with pytest.raises(TypeError, match="ClaudeCodeConfig was expected"):
        prepare(StandInAgentConfig(runtime_host="127.0.0.1:1234"), ())


def test_a_config_built_for_one_runtime_cannot_reach_another_s_factory():
    from offgrid.runtimes.lmstudio import connect
    from tests.doubles import StandInRuntimeConfig

    with pytest.raises(TypeError, match="LMStudioConfig was expected"):
        connect(StandInRuntimeConfig(host="127.0.0.1:1234"))


def test_the_layer_rule_names_no_module_that_is_gone():
    stale = sorted(_domain_in_the_contract() - (_modules() | _packages()))

    assert not stale, (
        f"`source_modules` in pyproject.toml names {stale}, which is not in "
        "src/offgrid. The contract is stated over a module that moved or went."
    )
