"""What windows a person set this session, and which row the slider is over.

The picker floats the slider over one row at a time and keeps what each model
was set to for the length of the session. That workflow is proven under the
keys at the picker seam; this proves the state it rests on — that a commit
records the window for the row that was opened and no other, that an abandoned
edit records nothing, and that the windows accumulate across the models.
"""

from offgrid.tui.window_edits import WindowEdits


def test_a_fresh_record_holds_no_windows():
    assert WindowEdits().windows == {}


def test_a_commit_records_the_window_for_the_opened_model():
    edits = WindowEdits()

    edits.begin("qwen")
    recorded = edits.commit(8192)

    assert recorded == "qwen"
    assert edits.windows == {"qwen": 8192}


def test_a_commit_with_nothing_open_records_no_window():
    edits = WindowEdits()

    recorded = edits.commit(8192)

    assert recorded is None
    assert edits.windows == {}


def test_a_second_commit_after_one_records_nothing_until_reopened():
    edits = WindowEdits()

    edits.begin("qwen")
    edits.commit(8192)
    recorded = edits.commit(4096)

    assert recorded is None
    assert edits.windows == {"qwen": 8192}


def test_an_abandoned_edit_records_no_window():
    edits = WindowEdits()

    edits.begin("qwen")
    edits.cancel()
    recorded = edits.commit(8192)

    assert recorded is None
    assert edits.windows == {}


def test_windows_accumulate_across_the_models():
    edits = WindowEdits()

    edits.begin("qwen")
    edits.commit(8192)
    edits.begin("llama")
    edits.commit(4096)

    assert edits.windows == {"qwen": 8192, "llama": 4096}
