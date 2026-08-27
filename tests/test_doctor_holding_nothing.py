"""What `offgrid doctor` reports when the runtime is holding no model.

Everything the report says apart from the model is readable without one, and
the one thing a run would do about it is written in the profile. So the case
is where the report is worth most.
"""

from typer.testing import CliRunner

from offgrid.cli import app
from offgrid.domain.running.dialect import Dialect
from tests.doubles import StandInAgent, answer_as_an_agent
from tests.lmstudio_server import answer_as_lm_studio
from tests.profiles import add_to_section

runner = CliRunner()

HELD_NOTHING = "model     nothing held"
UNKNOWN = ("          ceiling   unknown", "          window    unknown")


def _model_lines(stderr: str) -> list[str]:
    """Read back the block the model's lines are printed as.

    From the model's own line to the last line before the next label, so
    what a continuation line is attached to is part of what is asserted.

    :param stderr: What the command said.

    :return: The lines of the block, in the order they were printed.
    """
    lines = stderr.splitlines()
    start = lines.index(HELD_NOTHING)
    rest = lines[start + 1 :]
    ends = next(
        (at for at, line in enumerate(rest) if line.startswith("requests")), len(rest)
    )

    return lines[start : start + 1 + ends]


def test_doctor_says_when_the_runtime_holds_nothing(here, monkeypatch):
    # In the column with everything else it read, and marked unknown rather
    # than left out: a model line with no model behind it is not the same
    # statement as a runtime stating no number for one it holds.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(monkeypatch, cold={"a/cold-7b": 8192})

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert HELD_NOTHING in result.stderr
    assert result.stderr.splitlines()[-2:] != list(UNKNOWN)


def test_doctor_says_what_to_do_where_nothing_names_a_model_at_all(here, monkeypatch):
    # A profile asking for nothing and a runtime holding nothing is the one
    # pairing a run cannot get itself out of, and either half fixes it. Said
    # under the line it is about, which is what says which line it is about.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(monkeypatch, cold={"a/cold-7b": 8192})

    result = runner.invoke(app, ["doctor"])

    assert _model_lines(result.stderr) == [
        HELD_NOTHING,
        "              Load a model in the runtime, or name one under `model:` "
        "in the profile.",
        *UNKNOWN,
    ]


def test_doctor_sends_nobody_to_load_a_model_a_run_would_load_itself(here, monkeypatch):
    # A run reaches for the resident model only where nothing named one, so a
    # profile naming a model needs nothing held. Sending someone to load it by
    # hand is advice that is false about the profile in front of it.
    runner.invoke(app, ["setup"])
    add_to_section(here, "model", identifier="a/cold-7b")
    answer_as_lm_studio(monkeypatch, cold={"a/cold-7b": 8192})

    result = runner.invoke(app, ["doctor"])

    assert _model_lines(result.stderr) == [HELD_NOTHING, *UNKNOWN]
    # Said in the code even where the words say there is nothing to do by
    # hand: a runtime holding nothing is what this command went to find out.
    assert result.exit_code == 1


def test_doctor_reports_what_the_profile_asks_for_when_nothing_is_held(
    here, monkeypatch
):
    # The case that line is worth most in: a profile naming a model is a
    # statement about a model the runtime is not holding, so a report that
    # refuses to print it withholds it exactly where it answers something.
    runner.invoke(app, ["setup"])
    add_to_section(here, "model", identifier="a/cold-7b", context_window=32768)
    answer_as_lm_studio(monkeypatch, cold={"a/cold-7b": 8192})

    result = runner.invoke(app, ["doctor"])

    assert "requests  a/cold-7b at 32768" in result.stderr


def test_doctor_asks_for_a_model_where_a_window_is_asked_for_without_one(
    here, monkeypatch
):
    # A window and no model asks for the resident model at that window, so
    # this profile is one a run cannot get itself out of either — and the
    # `profile` line beside it says a run takes whatever is held.
    runner.invoke(app, ["setup"])
    add_to_section(here, "model", context_window=32768)
    answer_as_lm_studio(monkeypatch, cold={"a/cold-7b": 8192})

    result = runner.invoke(app, ["doctor"])

    assert "Load a model in the runtime" in result.stderr
    assert "requests  whatever is held, at 32768" in result.stderr


def test_doctor_reports_the_agent_when_nothing_is_held(here, monkeypatch):
    # None of it is the runtime's to answer, so none of it goes with the
    # model: which agent a run would start, what it speaks, and the smallest
    # window it starts in.
    answer_as_an_agent(
        monkeypatch, StandInAgent(dialect=Dialect.ANTHROPIC, context_floor=9000)
    )
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(monkeypatch, cold={"a/cold-7b": 8192})

    result = runner.invoke(app, ["doctor"])

    assert "speaking anthropic" in result.stderr
    assert "floor     9000" in result.stderr
