"""What a run says about a window the runtime did not grant it.

Two sentences, because offgrid knows two different things. Where it put the
window to the runtime and read the answer back, it says the runtime did not
grant it. Where that same window was already on record it asked for none this
run, so it says so and dates the refusal it is repeating rather than claiming
anything about what the runtime did or about what was already held.
"""

import json

import pytest
from typer.testing import CliRunner

from offgrid.cli import app
from offgrid.domain.running import discarded_windows
from tests.commands import answer_as_a_mac
from tests.launches import record_launch
from tests.lmstudio_server import RESIDENT, answer_as_lm_studio


def _hand_write(here, *, noticed_at: str, identifier: str = RESIDENT) -> None:
    """Write a record by hand, so a test can pin the day it was noticed.

    The stamp is the store's to make, which is what stops an unstamped record
    existing, so a test reading a date back writes it as a person would.

    :param here: Where the profile and what sits beside it are written.
    :param noticed_at: The day and time to put on the record.
    :param identifier: The model the record is about.
    """
    record = {
        "runtime": "lmstudio",
        "host": HOST,
        "identifier": identifier,
        "asked_for": ASKED_FOR,
        "served": 212224,
        "noticed_at": noticed_at,
    }

    (here / "discarded-windows.json").write_text(json.dumps([record]))


runner = CliRunner()
HOST = "127.0.0.1:1234"
ASKED_FOR = 40000
SERVED = 262_144


@pytest.fixture
def asked(monkeypatch):
    """What the runtime was asked to do, so a test can say it was not."""
    return answer_as_lm_studio(monkeypatch, holding={RESIDENT: 212224})


@pytest.fixture
def here(monkeypatch, tmp_path, asked):
    """Answer with a fixed machine, and write nowhere real."""
    answer_as_a_mac(monkeypatch, tmp_path)

    return tmp_path


def test_run_says_when_the_runtime_did_not_grant_the_window_asked_for(
    here, monkeypatch
):
    # offgrid asked and read the answer back, so it can say the runtime did
    # not grant it, and name both numbers.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(monkeypatch, cold={"a/other-7b": SERVED}, serves=SERVED)
    record_launch(monkeypatch)

    result = runner.invoke(
        app, ["run", "-m", "a/other-7b", "--context-window", str(ASKED_FOR)]
    )

    assert result.exit_code == 0
    assert (
        f"offgrid asked the runtime to hold a/other-7b at {ASKED_FOR} and it "
        f"is serving {SERVED}" in result.stderr
    )


def test_run_says_what_is_held_where_the_window_was_discarded_before(here, monkeypatch):
    # Nothing was put to the runtime this run, so the sentence claims nothing
    # about what it did or about what was already held — the model may have
    # been loaded in the same breath. It dates the refusal it repeats.
    runner.invoke(app, ["setup"])
    record_launch(monkeypatch)
    _hand_write(here, noticed_at="2026-08-21T14:31:07")

    result = runner.invoke(
        app, ["run", "-m", RESIDENT, "--context-window", str(ASKED_FOR)]
    )

    assert result.exit_code == 0
    assert (
        f"offgrid did not ask for {ASKED_FOR}: the runtime discarded that "
        f"window on 2026-08-21, and is serving {RESIDENT} at 212224" in result.stderr
    )


def test_run_claims_nothing_about_holding_a_model_it_loaded_this_run(here, monkeypatch):
    # A record means offgrid asked for no window, not that the model was
    # sitting there: it may have been loaded in the same breath, and it was
    # here. A sentence saying it was "already held" states something offgrid
    # never checked.
    runner.invoke(app, ["setup"])
    record_launch(monkeypatch)
    _hand_write(here, identifier="a/other-7b", noticed_at="2026-08-21T14:31:07")
    asked = answer_as_lm_studio(monkeypatch, cold={"a/other-7b": SERVED}, serves=SERVED)

    result = runner.invoke(
        app, ["run", "-m", "a/other-7b", "--context-window", str(ASKED_FOR)]
    )

    assert result.exit_code == 0
    assert asked["loaded"] == "a/other-7b"
    assert "already held" not in result.stderr
    assert f"offgrid did not ask for {ASKED_FOR}" in result.stderr


def test_doctor_names_the_file_to_delete_to_ask_for_the_window_again(here):
    # `doctor` is where a person looks when something is not what they asked
    # for, so it is where the way back is named. Deleting the file is the
    # only way to ask again, and a person who is not told has none.
    runner.invoke(app, ["setup"])
    _hand_write(here, noticed_at="2026-08-21T14:31:07")

    result = runner.invoke(app, ["doctor"])

    assert (
        f"discarded   {ASKED_FOR} was asked for on 2026-08-21 and 212224 "
        "served then, so offgrid is not asking again." in result.stderr
    )
    assert "discarded-windows.json" in result.stderr


def test_doctor_says_nothing_about_a_window_nothing_was_discarded_for(here):
    # A line about a thing that has not happened is noise in a command people
    # run when something already is.
    runner.invoke(app, ["setup"])

    result = runner.invoke(app, ["doctor"])

    assert "discarded" not in result.stderr


def test_a_second_run_does_not_put_a_refused_window_to_the_runtime_again(
    here, monkeypatch
):
    # End to end, with nothing written by hand: the first run asks and is
    # refused, the second reads that back and asks for nothing. Without the
    # first run keeping what it learned, the second pays the load again.
    runner.invoke(app, ["setup"])
    record_launch(monkeypatch)
    put = answer_as_lm_studio(monkeypatch, cold={"a/other-7b": SERVED}, serves=SERVED)

    first = runner.invoke(
        app, ["run", "-m", "a/other-7b", "--context-window", str(ASKED_FOR)]
    )

    assert first.exit_code == 0
    assert "offgrid asked the runtime to hold" in first.stderr
    assert put["window"] == ASKED_FOR

    held = answer_as_lm_studio(monkeypatch, holding={"a/other-7b": SERVED})

    second = runner.invoke(
        app, ["run", "-m", "a/other-7b", "--context-window", str(ASKED_FOR)]
    )

    assert second.exit_code == 0
    assert "offgrid did not ask for" in second.stderr
    # The release at the end of a run is owed either way; what a reload would
    # have added is a load, and there is none.
    assert held["loaded"] is None


def test_a_window_refused_before_a_later_one_is_still_not_asked_again(
    here, monkeypatch
):
    # Two windows put to the runtime in turn, and a third run goes back to the
    # first. Keeping only the last answer forgets the first, so the runtime is
    # asked a question it has answered and pays the load that answering costs.
    runner.invoke(app, ["setup"])
    record_launch(monkeypatch)
    answer_as_lm_studio(monkeypatch, cold={"a/other-7b": SERVED}, serves=SERVED)

    runner.invoke(app, ["run", "-m", "a/other-7b", "--context-window", str(ASKED_FOR)])

    answer_as_lm_studio(monkeypatch, holding={"a/other-7b": SERVED}, serves=SERVED)

    runner.invoke(app, ["run", "-m", "a/other-7b", "--context-window", "30000"])

    again = answer_as_lm_studio(
        monkeypatch, holding={"a/other-7b": SERVED}, serves=SERVED
    )

    third = runner.invoke(
        app, ["run", "-m", "a/other-7b", "--context-window", str(ASKED_FOR)]
    )

    assert third.exit_code == 0
    assert f"offgrid did not ask for {ASKED_FOR}" in third.stderr
    assert again["loaded"] is None


def test_run_says_nothing_where_the_runtime_grants_the_window_asked_for(
    here, monkeypatch
):
    # The path most runs take. A granted window recorded as a refusal would
    # make the next run stop asking for the one thing that was working.
    runner.invoke(app, ["setup"])
    record_launch(monkeypatch)
    answer_as_lm_studio(monkeypatch, cold={"a/other-7b": SERVED})

    result = runner.invoke(
        app, ["run", "-m", "a/other-7b", "--context-window", str(ASKED_FOR)]
    )

    assert result.exit_code == 0
    assert "offgrid asked the runtime to hold" not in result.stderr
    assert "offgrid did not ask for" not in result.stderr
    assert not (here / "discarded-windows.json").exists()


def test_a_refusal_of_another_window_is_put_to_the_runtime_and_kept(here, monkeypatch):
    # The record says 40000 was refused; this run asks for 30000, which the
    # runtime has never been shown. It is put, refused, and written down —
    # repeating the older sentence would date a refusal of a different number
    # and leave this one unrecorded, so every later run pays the load again.
    runner.invoke(app, ["setup"])
    record_launch(monkeypatch)
    _hand_write(here, identifier="a/other-7b", noticed_at="2026-08-21T14:31:07")
    put = answer_as_lm_studio(monkeypatch, cold={"a/other-7b": SERVED}, serves=SERVED)

    result = runner.invoke(
        app, ["run", "-m", "a/other-7b", "--context-window", "30000"]
    )

    assert result.exit_code == 0
    assert put["window"] == 30000
    assert "offgrid asked the runtime to hold a/other-7b at 30000" in result.stderr
    kept = json.loads((here / "discarded-windows.json").read_text())

    assert [record["asked_for"] for record in kept] == [ASKED_FOR, 30000]


def test_a_record_that_cannot_be_written_does_not_take_down_the_run(here, monkeypatch):
    # The model is held and the agent is about to start. Taking that away
    # over a record offgrid keeps for itself would cost the load twice, so it
    # is said and stepped over.
    runner.invoke(app, ["setup"])
    record_launch(monkeypatch)
    answer_as_lm_studio(monkeypatch, cold={"a/other-7b": SERVED}, serves=SERVED)

    # Only the records are out of reach: nothing to read, so the run gets that
    # far, and nowhere to write it once the runtime has answered.
    locked = here / "locked"
    locked.mkdir()
    monkeypatch.setattr(
        discarded_windows, "DEFAULT_PATH", locked / "discarded-windows.json"
    )
    locked.chmod(0o500)

    try:
        result = runner.invoke(
            app, ["run", "-m", "a/other-7b", "--context-window", str(ASKED_FOR)]
        )
    finally:
        locked.chmod(0o700)

    assert result.exit_code == 0
    assert "could not be written" in result.stderr
    assert "the next one asks for the window again" in result.stderr
