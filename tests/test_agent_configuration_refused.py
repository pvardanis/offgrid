"""What an agent refuses rather than guess about, asked of every adapter.

The other half of `tests/test_agent_configuration.py`: that file says what
`configure` writes and what it keeps, this one what it will not decide either
way. A file that is neither an edit nor an absence is the case where guessing
costs somebody a file, so it is refused and says so.

What a person reads is the whole of it, because only the adapter knows which
file to name — a refusal carrying neither the file nor what to do about it is a
wall with no door in it.

`tmp_path` is where offgrid keeps what it writes for the length of one test,
which is what lets these say what was written without knowing which files any
adapter uses.
"""

from pathlib import Path

import pytest

from offgrid.shared.exceptions import AgentSettingsError
from tests.agent_conformance import EVERY_AGENT, read_everything_under
from tests.agents_under_test import AgentUnderTest

pytestmark = EVERY_AGENT


def test_a_configuration_that_cannot_be_read_is_refused(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # Bytes that are not text are neither an edit to keep nor an absence to
    # write into, and guessing either way loses a person a file or hands an
    # agent one it cannot parse.
    #
    # One file at a time, because `configure` stops at the first it cannot
    # read: corrupting every file at once asks the suite about whichever the
    # adapter happens to reach first, and never about the rest.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)
    agent.configure()
    written = read_everything_under(tmp_path)

    for name in written:
        (tmp_path / name).write_bytes(b"\xff\xfe not text at all")

        with pytest.raises(AgentSettingsError) as refused:
            agent.configure()

        # The whole sentence: a refusal naming neither the file nor what to do
        # about it is a wall with no door in it.
        said = str(refused.value)
        assert name in said
        assert "cannot be read" in said
        assert "delete it and offgrid writes one" in said
        assert read_everything_under(tmp_path)[name] == b"\xff\xfe not text at all"

        (tmp_path / name).write_bytes(written[name])


def test_a_configuration_linked_to_a_target_that_is_gone_is_refused(
    agent_under_test: AgentUnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # A symlink whose target is gone reads as absent to everything that
    # follows it, so a check for absence says write — and the write follows
    # the link and creates a file at the far end instead of configuring this
    # one, somewhere offgrid never looked and with nothing said about it.
    agent = agent_under_test.prepare(monkeypatch, tmp_path)
    agent.configure()
    # It has to be a directory that is there. A link into one that is not
    # fails on the way past and looks like this test passing, which is the
    # accident rather than the guard.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    for name in read_everything_under(tmp_path):
        leading = tmp_path / name
        leading.unlink()
        # Flat inside it, so that every link has a directory to land in: one
        # pointing at a path whose parent is missing fails on the way past,
        # which reads as this test passing and guards nothing.
        leading.symlink_to(elsewhere / leading.name)

    with pytest.raises(AgentSettingsError) as refused:
        agent.configure()

    written_outside = sorted(path.name for path in elsewhere.iterdir())

    assert not written_outside, f"{written_outside} was written outside {tmp_path}"
    # The whole sentence, for the same reason as above.
    said = str(refused.value)
    assert "is a link to" in said
    assert "delete it and offgrid writes a file here" in said
