"""What a run says when the runtime states no window to size OpenCode to.

The launch carries no `limit` at all there, so OpenCode answers at its own
context default and its own output default and the runtime truncates the
prefix at whatever it is serving. That is met mid-session unless it is said
first, which is what a caution is. What the launch carries in that state is in
`tests/test_opencode.py`; what is here is what a person reads about it.
"""

import pytest
from typer.testing import CliRunner

from offgrid.agents.opencode.launching import MAX_OUTPUT_TOKENS
from offgrid.cli import app
from tests.launches import record_launch
from tests.lmstudio_server import RESIDENT, answer_as_lm_studio
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


def test_a_run_at_a_window_nobody_stated_says_what_it_costs(agent):
    # Both halves of the loss, because they are lost together: the schema
    # takes `context` and `output` as a pair, so the output cap goes with the
    # window rather than outliving it.
    caution = plan_for(agent, window=None).caution

    assert caution is not None
    assert "states no window" in caution
    assert str(MAX_OUTPUT_TOKENS) in caution


def test_it_says_both_ways_a_person_can_state_the_window_themselves(agent):
    # A number offgrid guessed is the same truncation arrived at by guessing,
    # so what is offered is the two places a person can state one: the flag
    # that holds the model at a window, and the file they already edit.
    caution = plan_for(agent, window=None).caution or ""

    assert "--context-window" in caution
    assert "limit" in caution
    assert "opencode.json" in caution


def test_the_run_that_is_sized_says_nothing_about_the_window(agent):
    # A sentence about an unsized run beside a sized one sends somebody
    # editing a file to fix what is already right.
    caution = plan_for(agent, window=32768).caution

    assert caution is not None
    assert "--context-window" not in caution


def test_what_a_person_loses_either_way_is_still_said(agent):
    # Project configuration is taken away whatever the window is, so the two
    # cautions are read together rather than one replacing the other.
    unsized = plan_for(agent, window=None).caution or ""

    assert "Project configuration is not read" in unsized


def test_run_says_it_before_it_starts_the_agent(here, monkeypatch):
    # Read before the session rather than halfway through one, wondering why
    # a conversation that fits was truncated.
    runner.invoke(app, ["setup"])
    add_to_section(here, "agent", name=NAMED)
    answer_as_lm_studio(monkeypatch, holding={RESIDENT: None})
    said: list = []
    record_launch(monkeypatch, order=said)
    monkeypatch.setattr("offgrid.cli.run.tell", lambda word: said.append(word))

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 0
    spoken = next(
        word for word in said if isinstance(word, str) and "--context-window" in word
    )
    assert said.index(spoken) < said.index(("started", NAMED))
