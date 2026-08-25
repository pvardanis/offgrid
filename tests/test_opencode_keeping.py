"""What offgrid keeps of an OpenCode configuration, and what it refuses.

The other half of the split that `tests/test_opencode_configuring.py` covers:
that file says what lands in a fresh directory, this one what happens to a file
that is already there.

This adapter is where a file that says nothing costs the most. It offers
nothing hosted and answers that from a constant, so `configure` is the only
thing that ever reads this file — where Claude Code's own guard reads its
settings back and refuses a run over them.
"""

import pytest

from offgrid.shared.exceptions import AgentSettingsError
from tests.opencode_bindings import SETTINGS, bind, read_written


@pytest.fixture(autouse=True)
def _nowhere_real(monkeypatch, tmp_path):
    """Keep the directory an agent derives for itself inside the test."""
    monkeypatch.setattr("offgrid.domain.running.agent.OFFGRID_HOME", tmp_path)


@pytest.fixture
def config_dir(tmp_path):
    """Where the agent keeps its own file, as its config derives it."""
    return tmp_path / "opencode"


def test_an_edited_configuration_is_left_as_a_person_left_it(config_dir):
    # Sharing is offgrid's default rather than offgrid's decision: somebody
    # who wants it back edits the file and keeps the edit.
    agent = bind()
    agent.configure()
    (config_dir / SETTINGS).write_text('{"share": "manual"}\n')

    agent.configure()

    assert read_written(config_dir)["share"] == "manual"


def test_a_configuration_holding_null_is_left_as_a_person_left_it(config_dir):
    # `null` is a document somebody could have left and is also how "nothing"
    # is spelled, so a run deciding what to write off the parsed value would
    # write over this one file and no other.
    config_dir.mkdir()
    (config_dir / SETTINGS).write_text("null\n")

    bind().configure()

    assert (config_dir / SETTINGS).read_text() == "null\n"


def test_a_configuration_cut_off_part_way_says_what_stopped_it(config_dir):
    # Half a file is neither an edit to keep nor an absence to write into, and
    # nothing downstream would say so: a run would start against a provider
    # entry that stops mid-key.
    config_dir.mkdir()
    (config_dir / SETTINGS).write_text('{"share": "disab')

    with pytest.raises(AgentSettingsError) as refused:
        bind().configure()

    # The whole sentence, because a refusal that does not say which file or
    # what to do about it is a wall with no door in it.
    said = str(refused.value)
    assert str(config_dir / SETTINGS) in said
    assert "is not readable as JSON" in said
    assert "Fix it, or delete it and offgrid writes one." in said


def test_a_configuration_that_cannot_be_written_says_what_stopped_it(
    tmp_path, monkeypatch
):
    # The command line reports offgrid's own errors and lets everything else
    # reach the terminal as a traceback, which is no use to whoever owns the
    # directory that would not take the file.
    in_the_way = tmp_path / "not-a-directory"
    in_the_way.write_text("")
    monkeypatch.setattr("offgrid.domain.running.agent.OFFGRID_HOME", in_the_way)

    with pytest.raises(AgentSettingsError) as refused:
        bind().configure()

    # The whole sentence, because a refusal naming neither the directory nor
    # what to do about it is a wall with no door in it.
    said = str(refused.value)
    assert str(in_the_way / "opencode") in said
    assert "cannot be written" in said
    assert "Fix what is there or what owns it, and run again." in said
