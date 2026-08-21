"""What offgrid keeps about a window a runtime was asked for and did not grant.

The fact is kept rather than the verdict — what was asked, what came back, and
when — so that whoever reads it decides what to do about it. A file that
cannot be read back is no memory rather than an error: offgrid wrote it, and a
run that lost it has a reload to pay and nothing else.
"""

from offgrid.domain.running.remembering import (
    DiscardedWindow,
    read_discarded_window,
    remember_discarded_window,
)

HOST = "127.0.0.1:1234"
IDENTIFIER = "a/held-7b"


def test_a_discarded_window_is_read_back_as_it_was_kept(tmp_path):
    # What was asked and what came back are both kept, because a later run
    # says both out loud and cannot recover either by asking again.
    kept = tmp_path / "discarded-windows.json"

    remember_discarded_window(
        DiscardedWindow(
            host=HOST, identifier=IDENTIFIER, asked_for=131_072, served=262_144
        ),
        kept,
    )
    read = read_discarded_window(HOST, IDENTIFIER, kept)

    assert read is not None
    assert read.asked_for == 131_072
    assert read.served == 262_144
