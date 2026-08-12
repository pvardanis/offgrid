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
    from offgrid.runtimes import RUNTIMES

    assert set(RUNTIMES) == set(RuntimeName)


def test_every_agent_offgrid_names_has_an_adapter_bound_to_it():
    from offgrid.agent import AgentName
    from offgrid.agents import AGENTS

    assert set(AGENTS) == set(AgentName)


def test_the_layer_rule_names_no_module_that_is_gone():
    stale = sorted(_domain_in_the_contract() - _modules())

    assert not stale, (
        f"`source_modules` in pyproject.toml names {stale}, which is not in "
        "src/offgrid. The contract is stated over a module that moved or went."
    )
