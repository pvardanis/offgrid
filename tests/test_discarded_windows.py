"""What a run says about a window the runtime did not grant it.

Two sentences, because offgrid knows two different things. Where it asked and
read the answer back, it can say the runtime did not grant what was asked for.
Where it found the model already held, it made no request at all, and the most
it can say is what is there and what the profile wanted — which is why the
second sentence cites the day the first one was true rather than repeating its
claim.
"""

import pytest
from typer.testing import CliRunner

from offgrid.cli import app
from offgrid.domain.running import remembering
from tests.commands import answer_as_a_mac
from tests.launches import record_launch
from tests.lmstudio_server import RESIDENT, answer_as_lm_studio

runner = CliRunner()
HOST = "127.0.0.1:1234"
ASKED_FOR = 40000
SERVED = 262_144


@pytest.fixture
def here(monkeypatch, tmp_path):
    """Answer with a fixed machine, and write nowhere real."""
    answer_as_lm_studio(monkeypatch, holding={RESIDENT: 212224})
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
    assert "asked" in result.stderr
    assert str(ASKED_FOR) in result.stderr
    assert str(SERVED) in result.stderr


def test_run_says_what_is_held_where_the_window_was_discarded_before(here, monkeypatch):
    # Nothing was asked of the runtime this run, so the sentence claims
    # nothing about what it did: it says what is there, and cites the day it
    # was told.
    runner.invoke(app, ["setup"])
    record_launch(monkeypatch)
    remembering.remember_discarded_window(
        remembering.DiscardedWindow(
            host=HOST,
            identifier=RESIDENT,
            asked_for=ASKED_FOR,
            served=212224,
            noticed_at="2026-08-21T14:31:07",
        ),
        here / "discarded-windows.json",
    )

    result = runner.invoke(
        app, ["run", "-m", RESIDENT, "--context-window", str(ASKED_FOR)]
    )

    assert result.exit_code == 0
    assert "already held at 212224" in result.stderr
    assert "discarded that window on 2026-08-21" in result.stderr


def test_doctor_names_the_file_to_delete_to_ask_for_the_window_again(here):
    # `doctor` is where a person looks when something is not what they asked
    # for, so it is where the way back is named. Deleting the file is the
    # only way to ask again, and a person who is not told has none.
    runner.invoke(app, ["setup"])
    remembering.remember_discarded_window(
        remembering.DiscardedWindow(
            host=HOST,
            identifier=RESIDENT,
            asked_for=ASKED_FOR,
            served=212224,
            noticed_at="2026-08-21T14:31:07",
        ),
        here / "discarded-windows.json",
    )

    result = runner.invoke(app, ["doctor"])

    assert "discarded-windows.json" in result.stderr
    assert "2026-08-21" in result.stderr


def test_doctor_says_nothing_about_a_window_nothing_was_discarded_for(here):
    # A line about a thing that has not happened is noise in a command people
    # run when something already is.
    runner.invoke(app, ["setup"])

    result = runner.invoke(app, ["doctor"])

    assert "discarded" not in result.stderr
