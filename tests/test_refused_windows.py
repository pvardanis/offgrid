"""Which windows a run is refused for, wherever the number came from.

A window states itself on a command line or in a profile, and the two ends it
is measured against — the agent's floor and the model's ceiling — do not care
which. What the refusals say about a number someone typed is covered beside
the flag; this is the same pair of refusals reached through the file.
"""

from typer.testing import CliRunner

from offgrid.cli import app
from tests.launches import record_launch
from tests.lmstudio_server import RESIDENT, SERVED, answer_as_lm_studio
from tests.profiles import add_to_section

runner = CliRunner()


def test_a_window_the_profile_asks_for_is_refused_against_the_agents_floor(
    here, monkeypatch
):
    # The refusals were written for a number someone typed. A number read out
    # of a file reaches them the same way, and the run is stopped before the
    # load rather than at the agent's own startup.
    runner.invoke(app, ["setup"])
    add_to_section(here, "model", context_window=8000)
    asked = answer_as_lm_studio(monkeypatch, holding={RESIDENT: SERVED})
    record_launch(monkeypatch)

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 1
    assert "below the agent's floor" in result.stderr
    assert asked["loaded"] is None


def test_a_window_the_profile_asks_for_is_refused_against_the_models_ceiling(
    here, monkeypatch
):
    runner.invoke(app, ["setup"])
    add_to_section(here, "model", context_window=300000)
    asked = answer_as_lm_studio(monkeypatch, holding={RESIDENT: SERVED}, ceiling=262144)
    record_launch(monkeypatch)

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 1
    assert "above" in result.stderr
    assert asked["loaded"] is None
