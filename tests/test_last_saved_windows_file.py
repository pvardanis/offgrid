"""What the last-saved-windows file holds, and which records it refuses.

Read as a file a person may have opened, the way the profile and the
discarded-windows file are: a record offgrid cannot make sense of is said out
loud rather than skipped, because the window the picker defaults a model to is
read from here and a silently dropped record is a default quietly lost. A file
that is not there is no memory rather than a fault — that is every model before
one is first saved.
"""

import json

import pytest
from offgrid.domain.running.last_saved_windows import (
    read_last_saved_windows,
    save_last_saved_window,
)

from offgrid.shared.exceptions import LastSavedWindowsUnreadableError

MODEL = "a/held-7b"
OTHER_MODEL = "a/other-7b"


def _kept(tmp_path):
    """Where the records go.

    :param tmp_path: The test's directory.
    :return: The file to keep them in.
    """
    return tmp_path / "last-saved-windows.json"


def _save(tmp_path, *, identifier=MODEL, window=131_072):
    """Keep one record, defaulting everything a test is not about.

    :param tmp_path: The test's directory.
    :param identifier: The model that was saved.
    :param window: The window it was saved at.
    """
    save_last_saved_window(
        identifier=identifier,
        window=window,
        file_path=_kept(tmp_path),
    )


def _hand_written(tmp_path, *records) -> None:
    """Write records the way a person editing the file would.

    :param tmp_path: The test's directory.
    :param records: The mappings to write.
    """
    _kept(tmp_path).write_text(json.dumps(list(records)))


# A record offgrid would have written, for a test to spoil one key of.
_WHOLE = {
    "identifier": MODEL,
    "window": 131_072,
}


def test_a_saved_window_reads_back_as_it_was_kept(tmp_path):
    _save(tmp_path, window=262_144)

    assert read_last_saved_windows(_kept(tmp_path)) == {MODEL: 262_144}


def test_a_second_model_is_kept_beside_the_first(tmp_path):
    _save(tmp_path, identifier=MODEL, window=1000)
    _save(tmp_path, identifier=OTHER_MODEL, window=2000)

    assert read_last_saved_windows(_kept(tmp_path)) == {MODEL: 1000, OTHER_MODEL: 2000}


def test_saving_a_model_again_moves_its_window(tmp_path):
    # One record per model: the store is what it was last saved at, not every
    # window it was ever saved at, so a fresh save replaces rather than adds.
    _save(tmp_path, window=1000)
    _save(tmp_path, window=3000)

    assert read_last_saved_windows(_kept(tmp_path)) == {MODEL: 3000}
    assert len(json.loads(_kept(tmp_path).read_text())) == 1


def test_saving_one_model_leaves_anothers_record_alone(tmp_path):
    _save(tmp_path, identifier=MODEL, window=1000)
    _save(tmp_path, identifier=OTHER_MODEL, window=2000)
    _save(tmp_path, identifier=MODEL, window=9000)

    assert read_last_saved_windows(_kept(tmp_path)) == {MODEL: 9000, OTHER_MODEL: 2000}


def test_a_model_with_no_record_has_no_entry(tmp_path):
    _save(tmp_path, identifier=MODEL)

    assert OTHER_MODEL not in read_last_saved_windows(_kept(tmp_path))


def test_a_file_that_is_not_there_is_no_memory(tmp_path):
    assert read_last_saved_windows(_kept(tmp_path)) == {}


def test_a_file_that_will_not_read_is_said_out_loud(tmp_path):
    _kept(tmp_path).write_text("{not json at all")

    with pytest.raises(LastSavedWindowsUnreadableError, match="could not be read"):
        read_last_saved_windows(_kept(tmp_path))


@pytest.mark.parametrize(
    ("what", "record"),
    [
        ("a window written as yes", {"window": True}),
        ("a window of no tokens", {"window": 0}),
        ("a window below zero", {"window": -1}),
        ("a window that is a word", {"window": "lots"}),
    ],
)
def test_a_record_offgrid_cannot_read_is_refused(tmp_path, what, record):
    # `yes` is the sharp one: a boolean is an integer to anything that does
    # not look, so it would otherwise be a window of one token.
    _hand_written(tmp_path, _WHOLE | record)

    with pytest.raises(LastSavedWindowsUnreadableError):
        read_last_saved_windows(_kept(tmp_path))


def test_a_key_offgrid_does_not_write_is_refused(tmp_path):
    # A typo in a hand-edited record is reported rather than read as a record
    # about nothing, which is how the profile is read too.
    _hand_written(tmp_path, _WHOLE | {"why": "because"})

    with pytest.raises(LastSavedWindowsUnreadableError):
        read_last_saved_windows(_kept(tmp_path))
