"""What a run takes away from the directory it was started in, and what it says.

A configuration there outranks everything offgrid writes, and one redirecting
the provider hangs rather than failing, so a run is started with project
configuration switched off. That is a thing a person loses, so the launch says
so and the command line says it before it starts anything. Both halves are
here, because they are one thing being asked about rather than two: the rest
of what a run derives is in `tests/test_opencode.py`, and the rest of what the
command line does with an `opencode` profile is in `tests/test_cli_opencode.py`.
"""

import pytest
from typer.testing import CliRunner

from offgrid.agents.opencode.cautioning import PROJECT_CONFIG_CAUTION
from offgrid.cli import app
from tests.launches import record_launch
from tests.opencode_bindings import bind, plan_for
from tests.profiles import add_to_section

runner = CliRunner()

NAMED = "opencode"


@pytest.fixture(autouse=True)
def _nowhere_real(monkeypatch, tmp_path):
    """Keep the directory an agent derives for itself inside the test."""
    monkeypatch.setattr("offgrid.domain.running.agent.OFFGRID_HOME", tmp_path)


@pytest.fixture
def agent():
    return bind()


@pytest.fixture
def launch(agent):
    return plan_for(agent)


def test_a_configuration_in_the_directory_run_from_cannot_reach_the_run(launch):
    # Measured on opencode 1.18.20: a configuration in the directory a person
    # runs from outranks the file offgrid writes, and one redirecting the
    # provider makes the run hang rather than fail — at a closed port as much
    # as at an unreachable one. The variable is written out rather than
    # imported, because a launch naming it something else would leave project
    # configuration read and importing the constant would rename both sides at
    # once. It is asked for as well as set, because a launch takes names back
    # out of what the agent inherits and one taken back out here would leave
    # the run reading project configuration while the caution says it does not.
    assert launch.env["OPENCODE_DISABLE_PROJECT_CONFIG"] == "1"
    assert "OPENCODE_DISABLE_PROJECT_CONFIG" not in launch.dropped


def test_the_launch_says_project_configuration_will_not_be_read(launch):
    # Losing it silently is what somebody would otherwise spend half a session
    # debugging, which is what a caution is for. It says which directories are
    # searched, because naming the one a person is standing in tells them a
    # file at the root of their repository survives, and it does not.
    assert launch.caution == (
        "Project configuration is not read for this run: an `opencode.json`, a "
        "`.opencode` directory and instructions such as `AGENTS.md` are "
        "skipped, in the directory you started from and every directory above "
        "it up to the project root. offgrid cannot outrank the providers, "
        "agents and permissions one of those adds, so it runs with none of "
        "them. Your own configuration under your home is read as usual. Start "
        "OpenCode yourself to use what a project states."
    )


def test_the_caution_says_the_same_thing_whatever_the_directory_holds(
    agent, tmp_path, monkeypatch
):
    # A guard rather than a slice: nothing on this path reads a directory, so
    # it cannot be made to fail today. What it stops is the wording being
    # decided later out of what is there, which would mean reimplementing
    # OpenCode's own upward walk, its stopping condition and both file
    # spellings to choose a sentence — and a walk that drifted from theirs
    # would say the wrong thing confidently.
    beside_nothing = plan_for(agent).caution
    assert beside_nothing is not None

    # Every kind the caution names, spelled out rather than taken from the
    # constant naming the file offgrid writes for itself: what belongs here is
    # a project's own configuration, and renaming offgrid's would otherwise
    # leave this planting nothing of the kind.
    (tmp_path / "opencode.json").write_text("{}")
    (tmp_path / "opencode.jsonc").write_text("{}")
    (tmp_path / "AGENTS.md").write_text("Say only BANANA.\n")
    (tmp_path / ".opencode").mkdir()
    monkeypatch.chdir(tmp_path)

    assert plan_for(agent).caution == beside_nothing


def test_run_says_it_before_it_starts_the_agent(here, monkeypatch):
    # Read before the session rather than halfway through one, wondering why
    # a file that has always worked did nothing. The wording is pinned above;
    # what is asked here is where it lands.
    runner.invoke(app, ["setup"])
    add_to_section(here, "agent", name=NAMED)
    order: list = []
    record_launch(monkeypatch, order=order)
    monkeypatch.setattr(
        "offgrid.cli.run.tell", lambda said: order.append(("said", said))
    )

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 0
    assert order.index(("said", PROJECT_CONFIG_CAUTION)) < order.index(
        ("started", NAMED)
    )
