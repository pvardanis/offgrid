"""What docs/architecture.md and the import contracts claim, against the tree.

Both enumerate the modules by hand, and both go stale the same silent way:
somebody adds a module, or splits one, and neither notices. A map that has
quietly stopped describing the code is worse than none, because it is still
read.

The contract's side matters more than the doc's. A module missing from
`source_modules` is not covered by the rule that the domain knows nothing
about adapters — it is outside the check rather than passing it, and nothing
else would say so.

This is a regression guard, not a slice: it passes the day it is written. It
was checked by taking a module out of each list in turn and watching it fail.
"""

import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
DOC = ROOT / "docs" / "architecture.md"
PYPROJECT = ROOT / "pyproject.toml"
SOURCE = ROOT / "src" / "offgrid"

ADAPTER_PACKAGES = ("agents", "leaderboards", "runtimes")
COMMAND_LINE = {"offgrid.cli"}

# Held here rather than derived, so that calling a module shared is a decision
# someone makes rather than something a heuristic infers. Anything shared is
# reachable from every layer, which is a thing to be sure about.
SHARED = {"offgrid.exceptions", "offgrid.say"}


def _modules() -> set[str]:
    """Every module in the package, as import-linter names them."""
    return {
        "offgrid." + ".".join(path.relative_to(SOURCE).with_suffix("").parts)
        for path in SOURCE.rglob("*.py")
        if path.name != "__init__.py"
    }


def _domain_in_the_contract() -> set[str]:
    """The modules the layer rule is stated over."""
    contracts = tomllib.loads(PYPROJECT.read_text())["tool"]["importlinter"][
        "contracts"
    ]
    forbidden = next(one for one in contracts if one["type"] == "forbidden")

    return set(forbidden["source_modules"])


def _adapters(modules: set[str]) -> set[str]:
    """The modules living inside an adapter package."""
    return {
        module
        for module in modules
        if module.split(".")[1] in ADAPTER_PACKAGES and module.count(".") > 1
    }


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
    modules = _modules()
    classified = _domain_in_the_contract() | _adapters(modules) | COMMAND_LINE | SHARED

    unclassified = sorted(modules - classified)

    assert not unclassified, (
        f"{unclassified} sits in no layer, so the import contract does not "
        "cover it. Add it to `source_modules` in pyproject.toml, or to SHARED "
        "here if every layer may reach it."
    )


def test_every_runtime_offgrid_names_has_an_adapter_bound_to_it():
    # Two places that cannot be one: an enum carrying its own factory would
    # be a domain type importing an adapter. A name with no entry raises a
    # KeyError at somebody's terminal, halfway through a run.
    from offgrid.runtime import RuntimeName
    from offgrid.runtimes import RUNTIME_CONFIGS, RUNTIMES

    assert set(RUNTIMES) == set(RuntimeName)
    assert set(RUNTIME_CONFIGS) == set(RuntimeName)


def test_every_agent_offgrid_names_has_an_adapter_bound_to_it():
    from offgrid.agent import AgentName
    from offgrid.agents import AGENT_CONFIGS, AGENTS

    assert set(AGENTS) == set(AgentName)
    assert set(AGENT_CONFIGS) == set(AgentName)


def test_every_config_an_adapter_declares_forbids_a_key_it_does_not_name():
    # The base configs are permissive, because a section belongs to whichever
    # adapter the name picks and the base cannot know what that one reads. A
    # subclass that forgot to narrow would accept junk in silence, which is
    # the failure this whole area exists to prevent.
    from offgrid.agent import AgentConfig
    from offgrid.agents import AGENTS
    from offgrid.runtime import RuntimeConfig
    from offgrid.runtimes import RUNTIMES

    # The registries are what import every adapter, and an adapter has to have
    # been imported for the config it declares to be a subclass yet.
    assert AGENTS and RUNTIMES

    declared = [
        config
        for config in (*AgentConfig.__subclasses__(), *RuntimeConfig.__subclasses__())
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

    with pytest.raises(TypeError, match="claude-code was handed StandInAgentConfig"):
        prepare(StandInAgentConfig(), ())


def test_a_config_built_for_one_runtime_cannot_reach_another_s_factory():
    from offgrid.runtimes.lmstudio import connect
    from tests.doubles import StandInRuntimeConfig

    with pytest.raises(TypeError, match="lmstudio was handed StandInRuntimeConfig"):
        connect(StandInRuntimeConfig(host="127.0.0.1:1234"))


def test_the_layer_rule_names_no_module_that_is_gone():
    stale = sorted(_domain_in_the_contract() - _modules())

    assert not stale, (
        f"`source_modules` in pyproject.toml names {stale}, which is not in "
        "src/offgrid. The contract is stated over a module that moved or went."
    )
