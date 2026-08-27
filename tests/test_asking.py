"""What a run will ask for, readable before the run pays for it.

Every other line `doctor` prints is a reading of what is: the model held, the
window it is served at, what the agent speaks. This is the instruction the
next run carries, and until it was printed the two could only be compared by
making the run. Read at the `offgrid doctor` seam, because the comparison is
the report rather than anything the domain returns.
"""

from re import findall

from typer.testing import CliRunner

from offgrid.cli import app
from offgrid.shared.wording import LINE_WIDTH
from tests.lmstudio_server import RESIDENT, SERVED, answer_as_lm_studio
from tests.profiles import add_to_section

runner = CliRunner()

# A window nothing is serving, so what the profile asks for and what the
# runtime answers cannot be read as the same number. The name is one the
# runtime does not hold, for the same reason.
ASKED = 131072
WANTED = "a/hand-written-7b"

# Where every value in the report starts, counted from the start of the line:
# a label at the left, or an indented one narrowed by as much as it is in.
COLUMN = 12


def test_doctor_says_the_model_and_window_the_profile_asks_for(here):
    runner.invoke(app, ["setup"])
    add_to_section(here, "model", identifier=RESIDENT, context_window=ASKED)

    result = runner.invoke(app, ["doctor"])

    assert f"requests    {RESIDENT} at {ASKED}" in result.stderr


def test_doctor_says_a_profile_that_asks_for_nothing_asks_for_nothing(here):
    # What `setup` writes: both keys there to be edited, and neither said. A
    # line printed empty reads as a number nobody could find rather than as
    # the run it describes, which is against whatever is already held.
    runner.invoke(app, ["setup"])

    result = runner.invoke(app, ["doctor"])

    assert "requests    asks for nothing, so a run takes whatever is held" in (
        result.stderr
    )


def test_doctor_says_a_model_named_without_a_window_inherits_one(here):
    # Half a statement is not half a line: the window key being empty means
    # the runtime's own is kept, which is a thing a run does rather than a
    # number missing from the file.
    runner.invoke(app, ["setup"])
    add_to_section(here, "model", identifier=WANTED)

    result = runner.invoke(app, ["doctor"])

    assert f"requests    {WANTED}, at whatever it is served at" in result.stderr
    # The issue's own example: a profile naming one model against a runtime
    # holding another. Both names on screen is the whole of what it asked for.
    assert f"model       {RESIDENT}" in result.stderr


def test_doctor_says_a_window_asked_for_without_a_model_lands_on_the_resident_one(
    here,
):
    # A window with no name is a standing instruction, unlike the flag it
    # mirrors: it says "the resident model, at this window", and which model
    # that is depends on what the runtime happens to be holding.
    runner.invoke(app, ["setup"])
    add_to_section(here, "model", context_window=ASKED)

    result = runner.invoke(app, ["doctor"])

    assert f"requests    whatever is held, at {ASKED}" in result.stderr


def test_doctor_shows_a_window_the_runtime_is_not_serving_without_loading(
    here, monkeypatch
):
    # The whole of what this line is for: two numbers a reader can compare,
    # for the price of neither. Every line of the report was true before and
    # none of them was the one the next run would ask for.
    asked = answer_as_lm_studio(monkeypatch, holding={RESIDENT: SERVED})
    runner.invoke(app, ["setup"])
    add_to_section(here, "model", identifier=RESIDENT, context_window=ASKED)

    result = runner.invoke(app, ["doctor"])

    assert f"  window    {SERVED}" in result.stderr
    assert f"requests    {RESIDENT} at {ASKED}" in result.stderr
    assert asked["order"] == []


def test_doctor_reports_in_one_column(here):
    # The report is read down the labels, so what the new line has to do is
    # land where the others do. Adding it cost the line below it its padding
    # once, and nothing said so.
    runner.invoke(app, ["setup"])

    result = runner.invoke(app, ["doctor"])

    # A line that carries on from the one above it is indented to the column
    # rather than labelled, which is what tells the two apart. A heading is
    # the third kind: it labels the lines under it and says nothing itself,
    # so it has no value at the column and is only a heading if something
    # indented follows it.
    lines = [line for line in result.stderr.splitlines() if line]
    unindented = [line for line in lines if not line.startswith(" ")]
    labelled = [line for line in unindented if len(line.split("  ")) > 1]
    labels = [line.split(" ")[0] for line in labelled]

    assert "requests" in labels
    # Where each value starts, rather than how each label is padded: a label
    # of exactly the column's width passes the second reading and still puts
    # its value one place further out than every other line.
    assert all(line[COLUMN] != " " for line in labelled)
    assert all(
        line[:COLUMN] == label.ljust(COLUMN)
        for line, label in zip(labelled, labels, strict=True)
    )
    # Every heading introduces something. One that does not is a label whose
    # value went missing, which reads as a fact the report failed to state.
    headings = [line for line in unindented if line not in labelled]

    assert headings, "no heading is in the report, so this checks nothing"
    assert all(
        lines[lines.index(heading) + 1].startswith(" ") for heading in headings
    ), f"{headings} introduces nothing indented under it"


def test_doctor_breaks_a_long_sentence_at_the_indent_it_started_on(here):
    # A sentence wider than the terminal is wrapped by the terminal at the
    # left margin, which lands the rest of it under the labels rather than
    # under the line it belongs to. A command inside one is held together,
    # since a command broken across lines is one somebody pastes and watches
    # fail.
    runner.invoke(app, ["setup"])

    result = runner.invoke(app, ["doctor"])

    # A line with nowhere to break is left alone: a path is one word, and one
    # broken over two lines is a path to nothing.
    lines = [line for line in result.stderr.splitlines() if line]
    prose = [line for line in lines if " " in line.strip()]
    wrapped = [line for line in prose if len(line) > LINE_WIDTH]

    assert not wrapped, f"{wrapped} is wider than a line, so a terminal breaks it"
    assert any(len(line) > LINE_WIDTH / 2 for line in lines), (
        "no line in the report is long enough to have been wrapped, so this "
        "checks nothing"
    )
    for command in findall(r"`[^`]*`", result.stderr):
        assert any(command in line for line in lines), (
            f"{command} is broken across two lines"
        )
