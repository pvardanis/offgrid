"""Which of the three settles a run: the command line, the profile, the runtime.

A flag beats the profile, and the profile beats whatever the runtime was
already serving. Read at the `offgrid run` seam, because precedence shows only
in what the runtime was asked to hold and what the agent was started against.
"""

from typer.testing import CliRunner

from offgrid.cli import app
from tests.launches import record_launch
from tests.lmstudio_server import RESIDENT, SERVED, answer_as_lm_studio
from tests.profiles import add_to_section, drop_section

runner = CliRunner()


def test_a_profile_with_no_section_runs_against_what_the_runtime_holds(
    here, monkeypatch
):
    # A guard rather than a slice: `setup` writes the section now, so the only
    # way to a profile without one is a hand-edit — which is when nothing else
    # is watching. The run costs no load and asks for no window.
    runner.invoke(app, ["setup"])
    drop_section(here, "model")
    asked = answer_as_lm_studio(monkeypatch, holding={RESIDENT: SERVED})
    started = record_launch(monkeypatch)

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 0
    assert asked["loaded"] is None
    assert asked["window"] is None
    assert started["env"]["ANTHROPIC_MODEL"] == RESIDENT


def test_the_profile_names_the_model_when_the_command_line_does_not(here, monkeypatch):
    runner.invoke(app, ["setup"])
    add_to_section(here, "model", identifier="a/other-7b")
    asked = answer_as_lm_studio(
        monkeypatch, holding={RESIDENT: SERVED}, cold={"a/other-7b": 32768}
    )
    record_launch(monkeypatch)

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 0
    assert asked["loaded"] == "a/other-7b"


def test_the_command_line_beats_the_profile(here, monkeypatch):
    runner.invoke(app, ["setup"])
    add_to_section(here, "model", identifier="a/from-profile-7b")
    asked = answer_as_lm_studio(
        monkeypatch, cold={"a/from-profile-7b": 32768, "a/asked-for-7b": 32768}
    )
    started = record_launch(monkeypatch)

    runner.invoke(app, ["run", "-m", "a/asked-for-7b"])

    assert asked["loaded"] == "a/asked-for-7b"
    assert started["env"]["ANTHROPIC_MODEL"] == "a/asked-for-7b"


def test_a_window_in_the_profile_is_asked_for_without_anyone_typing_it(
    here, monkeypatch
):
    # The whole of what the section is for: written down once, every run gets
    # it, and the runtime is asked rather than left to serve what it recalled.
    runner.invoke(app, ["setup"])
    add_to_section(here, "model", context_window=40000)
    asked = answer_as_lm_studio(monkeypatch, holding={RESIDENT: SERVED})
    record_launch(monkeypatch)

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 0
    assert asked["window"] == 40000
    assert "window 40000" in result.stderr


def test_the_window_on_the_command_line_beats_the_one_in_the_profile(here, monkeypatch):
    # A different window for one run is what the flag is for, and editing the
    # file to get it is the thing the flag exists to avoid.
    runner.invoke(app, ["setup"])
    add_to_section(here, "model", context_window=40000)
    asked = answer_as_lm_studio(monkeypatch, holding={RESIDENT: SERVED})
    record_launch(monkeypatch)

    result = runner.invoke(app, ["run", "--context-window", "64000"])

    assert result.exit_code == 0
    assert asked["window"] == 64000


def test_a_model_named_on_the_command_line_keeps_the_window_the_profile_asks_for(
    here, monkeypatch
):
    # The two keys are beaten one at a time. A flag naming only the model that
    # dropped the window would run at whatever the runtime recalled, which is
    # the number the profile was written to stop being the answer.
    runner.invoke(app, ["setup"])
    add_to_section(here, "model", identifier="a/from-profile-7b", context_window=40000)
    asked = answer_as_lm_studio(
        monkeypatch, cold={"a/from-profile-7b": 131072, "a/asked-for-7b": 131072}
    )
    record_launch(monkeypatch)

    result = runner.invoke(app, ["run", "-m", "a/asked-for-7b"])

    assert result.exit_code == 0
    assert asked["loaded"] == "a/asked-for-7b"
    assert asked["window"] == 40000


def test_a_model_flag_naming_nothing_is_a_sentence_rather_than_a_traceback(
    here, monkeypatch
):
    # `-m "$MODEL"` with the variable unset is how this arrives. Read as no
    # name it runs against whatever is resident; refused by the type alone it
    # reaches the terminal as a validator's block of text.
    runner.invoke(app, ["setup"])
    record_launch(monkeypatch)

    result = runner.invoke(app, ["run", "-m", ""])

    assert result.exit_code == 1
    assert "--model" in result.stderr
    assert "Traceback" not in result.stderr
