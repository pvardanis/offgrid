"""What the discarded-windows file holds, and which records it refuses.

Read as a file a person may have opened, the way the profile is: a record
offgrid cannot make sense of is said out loud rather than skipped, because a
run that silently reads no memory asks for a window it has already been
refused and pays the reload for it. A file that is not there is no memory
rather than a fault.
"""

import json

import pytest

from offgrid.domain.running.discarded_windows import (
    read_discarded_windows,
    save_discarded_window,
)
from offgrid.shared.exceptions import DiscardedWindowsUnreadableError

HOST = "127.0.0.1:1234"
MODEL = "a/held-7b"
OTHER_MODEL = "a/other-7b"


def _kept(tmp_path):
    """Where the records go.

    :param tmp_path: The test's directory.
    :return: The file to keep them in.
    """
    return tmp_path / "discarded-windows.json"


def _save(tmp_path, *, host=HOST, identifier=MODEL, asked_for=1000, served=2000):
    """Keep one record, defaulting everything a test is not about.

    :param tmp_path: The test's directory.
    :param host: Address the runtime listens on.
    :param identifier: The model that was asked for.
    :param asked_for: The window the run asked to hold it at.
    :param served: The window the runtime served instead.
    """
    save_discarded_window(
        host=host,
        identifier=identifier,
        asked_for=asked_for,
        served=served,
        file_path=_kept(tmp_path),
    )


def _hand_written(tmp_path, *records) -> None:
    """Write records the way a person editing the file would.

    :param tmp_path: The test's directory.
    :param records: The mappings to write.
    """
    _kept(tmp_path).write_text(json.dumps(list(records)))


def test_a_record_reads_back_as_it_was_kept(tmp_path):
    _save(tmp_path, asked_for=131_072, served=262_144)

    read = read_discarded_windows(HOST, _kept(tmp_path)).get(MODEL)

    assert read is not None
    assert (read.asked_for, read.served) == (131_072, 262_144)


def test_a_second_answer_about_one_model_replaces_the_first(tmp_path):
    # A runtime that answered differently is described by what it just did.
    _save(tmp_path, asked_for=1000, served=2000)
    _save(tmp_path, asked_for=3000, served=4000)

    read = read_discarded_windows(HOST, _kept(tmp_path)).get(MODEL)

    assert read is not None
    assert (read.asked_for, read.served) == (3000, 4000)


def test_a_record_is_about_one_model_on_one_server(tmp_path):
    # Keyed on both, because two models on one runtime disagree about this
    # and one model may be reached at two addresses.
    _save(tmp_path)

    assert read_discarded_windows(HOST, _kept(tmp_path)).get(OTHER_MODEL) is None
    assert read_discarded_windows("127.0.0.1:9999", _kept(tmp_path)).get(MODEL) is None
    assert read_discarded_windows(HOST, _kept(tmp_path)).get(MODEL) is not None


def test_replacing_one_record_leaves_the_others_alone(tmp_path):
    _save(tmp_path, asked_for=1000)
    _save(tmp_path, identifier=OTHER_MODEL, asked_for=5, served=6)
    _save(tmp_path, asked_for=3000)

    assert read_discarded_windows(HOST, _kept(tmp_path)).get(OTHER_MODEL) is not None


def test_a_file_that_is_not_there_is_no_memory(tmp_path):
    assert read_discarded_windows(HOST, _kept(tmp_path)).get(MODEL) is None


def test_a_file_that_will_not_read_is_said_out_loud(tmp_path):
    _kept(tmp_path).write_text("{not json at all")

    with pytest.raises(DiscardedWindowsUnreadableError, match="could not be read"):
        read_discarded_windows(HOST, _kept(tmp_path)).get(MODEL)


@pytest.mark.parametrize(
    ("what", "record"),
    [
        ("a window written as yes", {"asked_for": True, "served": 2000}),
        ("a window of no tokens", {"asked_for": 0, "served": 2000}),
        ("a window below zero", {"asked_for": -1, "served": 2000}),
        ("a window that is a word", {"asked_for": "lots", "served": 2000}),
    ],
)
def test_a_record_offgrid_cannot_read_is_refused(tmp_path, what, record):
    # `yes` is the sharp one: a boolean is an integer to anything that does
    # not look, so it would otherwise be a window of one token.
    _hand_written(
        tmp_path,
        {"host": HOST, "identifier": MODEL, "noticed_at": "2026-08-21T14:31:07"}
        | record,
    )

    with pytest.raises(DiscardedWindowsUnreadableError):
        read_discarded_windows(HOST, _kept(tmp_path)).get(MODEL)


def test_a_key_offgrid_does_not_write_is_refused(tmp_path):
    # A typo in a hand-edited record is reported rather than read as a record
    # about nothing, which is how the profile is read too.
    _hand_written(
        tmp_path,
        {
            "host": HOST,
            "identifier": MODEL,
            "asked_for": 1000,
            "served": 2000,
            "noticed_at": "2026-08-21T14:31:07",
            "why": "because",
        },
    )

    with pytest.raises(DiscardedWindowsUnreadableError):
        read_discarded_windows(HOST, _kept(tmp_path)).get(MODEL)


def test_saving_for_one_runtime_leaves_another_runtimes_record_alone(tmp_path):
    # The record is about a model on a server, so replacing one runtime's
    # answer must not delete another's about the same model — that runtime
    # would go back to asking, and paying the load for it.
    _save(tmp_path, host=HOST, asked_for=1000)
    _save(tmp_path, host="127.0.0.1:9999", asked_for=2000)

    kept = read_discarded_windows(HOST, _kept(tmp_path))
    other = read_discarded_windows("127.0.0.1:9999", _kept(tmp_path))

    assert kept[MODEL].asked_for == 1000
    assert other[MODEL].asked_for == 2000


def test_one_model_keeps_one_record_however_often_it_is_refused(tmp_path):
    # What the replacing buys is a file that does not grow without bound: the
    # reading takes the last record for a model either way.
    _save(tmp_path, asked_for=1000)
    _save(tmp_path, asked_for=2000)
    _save(tmp_path, asked_for=3000)

    assert len(json.loads(_kept(tmp_path).read_text())) == 1
