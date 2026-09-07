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
was checked by taking a module out of the map, filing one under the wrong
layer, a package out of every layer, a layer out of the contract that names
them all, a registry entry out of its dict, and by pointing a module at a
concrete adapter — and watching each fail.
"""

import ast
import re
import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import BaseModel

ROOT = Path(__file__).parent.parent
DOC = ROOT / "docs" / "architecture.md"
PYPROJECT = ROOT / "pyproject.toml"
SOURCE = ROOT / "src" / "offgrid"


def _contracts() -> list[dict]:
    """Every import contract, as pyproject states them."""
    return tomllib.loads(PYPROJECT.read_text())["tool"]["importlinter"]["contracts"]


def _the_contract_where(predicate: Callable[[dict], bool], *, named: str) -> dict:
    """The one contract a predicate holds for.

    :param predicate: What singles the contract out.
    :param named: What that contract is, said in the error if it is gone or
        no longer the only one.

    :return: The one contract the predicate holds for.

    :raise LookupError: If no contract matches, so a contract this test reads
        being renamed or removed is named rather than raising a bare
        `StopIteration` that says nothing about what to do; or if more than
        one matches, so a predicate that has stopped singling one out is said
        rather than silently narrowing to whichever the file lists first.
    """
    matching = [one for one in _contracts() if predicate(one)]

    if len(matching) > 1:
        raise LookupError(
            f"more than one import contract in pyproject.toml is {named}: "
            f"{[one['name'] for one in matching]}. The predicate here no longer "
            "singles one out; tighten it, or split this helper."
        )

    if not matching:
        raise LookupError(
            f"no import contract in pyproject.toml is {named}. A contract this "
            "test reads was renamed or removed; restore it, or fix the predicate."
        )

    return matching[0]


def _adapter_packages() -> set[str]:
    """Every adapter package, from the contract holding them apart.

    The `independence` contract that keeps one adapter from reaching another
    names each adapter package, and no other independence contract names a
    top-level package — the other holds two halves of the domain apart. Read
    the adapters from there rather than by hand, so an adapter added to that
    contract is one this file already knows about.

    :return: The packages a concrete adapter lives under.
    """
    contract = _the_contract_where(
        lambda one: (
            one["type"] == "independence"
            and all(
                not module.startswith("offgrid.domain") for module in one["modules"]
            )
        ),
        named="the independence contract holding the adapters apart",
    )

    return set(contract["modules"])


def _the_shared_contract() -> dict:
    """The `forbidden` contract stating the shared layer reaches nothing.

    Singled out by its source rather than its prose, and pinned to `forbidden`
    so that a contract of another type carrying the same source could not be
    read in its place and change what the layers mean under this file's feet.

    :return: The contract forbidding the shared layer every other layer.
    """
    return _the_contract_where(
        lambda one: (
            one.get("type") == "forbidden"
            and one.get("source_modules") == ["offgrid.shared"]
        ),
        named="the forbidden contract stating the shared layer reaches nothing",
    )


def _every_layer() -> set[str]:
    """Every layer, from the one contract that names them all.

    `shared/` is innermost — reachable from every layer — so the contract
    forbidding it the rest names each of the others, and names shared itself as
    its source. Read the layers from there rather than listing them again, so
    that a layer dropped from the contract is a layer this check stops seeing,
    and says so rather than going on covering it on faith.

    :return: Every package a layer is stated over.
    """
    contract = _the_shared_contract()

    return set(contract["source_modules"]) | set(contract["forbidden_modules"])


def _layers_in_the_tree() -> set[str]:
    """Every layer there is, as the top-level packages under offgrid.

    A layer is a package directly under `offgrid`, so the tree is the whole
    statement of which layers exist. Read from it rather than listed, so a
    layer added to the tree is one this file already counts.

    :return: Every top-level package, as an import statement names it.
    """
    return {
        f"offgrid.{child.name}"
        for child in SOURCE.iterdir()
        if child.is_dir() and child.name != "__pycache__"
    }


# The map's layer headings, each owning the top-level packages filed under it.
# The map is read to find where a change goes, so a module named under the
# wrong heading answers that question wrongly — which is worse than a missing
# line, because it answers. Held here rather than derived, so that which
# package is an adapter and which is the screen is a decision, not a heuristic.
MAP_LAYERS = {
    "**command line**": {"cli"},
    "**the screen**": {"tui"},
    "**adapters**": {"runtimes", "agents", "leaderboards"},
    "**domain**": {"domain"},
    "**shared**": {"shared"},
}


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
        for package in _adapter_packages()
        for adapter in (SOURCE / package.rsplit(".", 1)[-1]).iterdir()
        if adapter.name != "__init__.py"
        and adapter.name != "__pycache__"
        and (adapter.suffix == ".py" or adapter.is_dir())
    }


def _reached_by(node: ast.ImportFrom, within: str) -> str:
    """Where a `from` import reaches, as an absolute name.

    A relative import names the same module as an absolute one and is only
    written differently, so it is resolved rather than skipped: `from
    .runtimes import lmstudio` in a command reaches the adapter exactly as far.

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


def _stated_in_a_contract() -> set[str]:
    """Every module a `forbidden` contract is stated over.

    Read from all of them rather than one by name, so that a layer added with
    a contract of its own is covered by having one rather than by somebody
    remembering this file. An `independence` contract states no source, and
    covers its modules from both directions instead.
    """
    return {module for one in _contracts() for module in one.get("source_modules", ())}


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


def _module_map() -> dict[str, set[str]]:
    """The filenames the map lists in fenced code, gathered per layer heading.

    Only the blocks under **The modules** count, and only the `.py` names in
    their fenced lines: a name in a sentence of prose, or under another layer's
    heading, is not the map placing a module — it is the string happening to be
    in the file. Names rather than raw text so a basename is matched whole, not
    as a substring of a longer filename beside it.

    :return: Each layer heading, mapped to the filenames listed beneath it.
    """
    section = DOC.read_text().split("## The modules")[1].split("\n## ")[0]

    blocks: dict[str, set[str]] = {}
    heading, fenced = None, False

    for line in section.splitlines():
        if line in MAP_LAYERS:
            heading, fenced = line, False
        elif line.startswith("```"):
            fenced = not fenced
        elif fenced and heading:
            blocks.setdefault(heading, set()).update(re.findall(r"\w+\.py", line))

    return blocks


def _named_under_its_layer(module: str, blocks: dict[str, set[str]]) -> bool:
    """Whether the map lists a module under the heading its package belongs to.

    The layer is the module's top-level package — `offgrid.cli.binding` is the
    command line — so a `cli/` module listed under **adapters** is not named
    under its layer, however plainly the basename reads elsewhere.

    :param module: The module to place, as import-linter names it.
    :param blocks: The map's filenames, per layer heading, from `_module_map`.

    :return: Whether the basename is listed under that layer.
    """
    package = module.split(".")[1]

    heading = next(
        (h for h, packages in MAP_LAYERS.items() if package in packages), None
    )

    basename = module.rsplit(".", 1)[-1] + ".py"

    return heading is not None and basename in blocks.get(heading, set())


def test_the_map_names_every_module_under_its_layer():
    blocks = _module_map()

    misplaced = sorted(
        module for module in _modules() if not _named_under_its_layer(module, blocks)
    )

    assert not misplaced, (
        f"docs/architecture.md does not name {misplaced} under the layer each "
        "belongs to. Add each to the map's code block beneath the heading for "
        "its package, or move it there from wherever it is now."
    )


def test_every_module_is_covered_by_the_layer_rule():
    named = _stated_in_a_contract() | _every_layer()

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
    from offgrid.runtimes import MODEL_DOWNLOAD_INSTRUCTIONS, RUNTIME_CONFIGS, RUNTIMES

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
    assert set(MODEL_DOWNLOAD_INSTRUCTIONS) == set(RuntimeName), _say_what_to_bind(
        set(RuntimeName),
        set(MODEL_DOWNLOAD_INSTRUCTIONS),
        enum="RuntimeName",
        registry="MODEL_DOWNLOAD_INSTRUCTIONS",
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


def test_every_agent_offgrid_names_has_somewhere_to_be_got_from():
    # A machine without the agent is sent to the page it is published from,
    # and `say_where_an_agent_comes_from` answers a sentence about offgrid
    # being at fault rather than refusing, so that one line failing does not
    # take a whole report with it. This is what keeps that sentence unread.
    from offgrid.domain.running.agent import AgentName
    from offgrid.domain.running.agent_presence import WHERE_AGENTS_COME_FROM

    assert set(WHERE_AGENTS_COME_FROM) == set(AgentName), _say_what_to_bind(
        set(AgentName),
        set(WHERE_AGENTS_COME_FROM),
        enum="AgentName",
        registry="WHERE_AGENTS_COME_FROM",
        module="offgrid/domain/running/agent_presence.py",
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


def test_the_shared_layer_is_forbidden_every_other_layer():
    # shared is innermost: reachable from every layer, reaching none. The
    # contract stating so is the whole list of which layers there are, and a
    # layer dropped from it is a layer shared may now reach unnoticed —
    # import-linter cannot see a forbidden contract weaken, only break. This
    # is what does.
    forbidden = set(_the_shared_contract()["forbidden_modules"])
    every_other = _layers_in_the_tree() - {"offgrid.shared"}

    adrift = sorted(forbidden ^ every_other)

    assert not adrift, (
        f"{adrift} is in the shared-layer contract's forbidden_modules or the "
        "tree's layers and not the other. shared is reachable from every layer "
        "and must reach none, so forbidden_modules in pyproject.toml should "
        "name every top-level package but shared: add what is missing, or drop "
        "what is gone."
    )


def test_the_layer_rule_names_no_module_that_is_gone():
    stale = sorted(_stated_in_a_contract() - (_modules() | _packages()))

    assert not stale, (
        f"`source_modules` in pyproject.toml names {stale}, which is not in "
        "src/offgrid. The contract is stated over a module that moved or went."
    )
