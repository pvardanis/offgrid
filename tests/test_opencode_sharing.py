"""What OpenCode's own reading says about a transcript leaving this machine.

The conformance suite asks every adapter that a run which could publish is
stopped. What is here is OpenCode's own half: the argument `opencode run` takes
for it, which no reading of a file can see, and the file shapes a person can
leave behind that the key cannot simply be read out of.

`tests/test_cli_opencode_leaving.py` asks the same things at the command, which
is where a person meets them.
"""

import pytest

from offgrid.agents.opencode.sharing import SHARING_ARGUMENT, read_transcript_sharing
from offgrid.domain.running.leaving import Status
from offgrid.shared.exceptions import AgentSettingsError

SETTLED = '{"share": "disabled"}'


def _read(tmp_path, body: str = SETTLED, passthrough: tuple[str, ...] = ()):
    """Ask the reading about a configuration and a command line.

    :param tmp_path: Where the configuration is written.
    :param body: What the configuration file holds.
    :param passthrough: What was handed to the agent unchanged.

    :return: What the reading answered.
    """
    settings = tmp_path / "opencode.json"
    settings.write_text(body)

    return read_transcript_sharing(settings, passthrough)


@pytest.mark.parametrize(
    "passthrough",
    [
        ("run", "say something", SHARING_ARGUMENT),
        (SHARING_ARGUMENT,),
        (f"{SHARING_ARGUMENT}=true",),
    ],
    ids=["after a prompt", "alone", "joined to its value"],
)
def test_an_argument_asking_to_share_beats_a_file_that_denies_it(tmp_path, passthrough):
    # The hole this file was written for. `opencode run --share` shares the
    # session, no reading of the configuration can see it, and `run` hands the
    # whole command line through — so a file saying `disabled` was answering a
    # question nobody asked.
    found = _read(tmp_path, passthrough=passthrough)

    assert found.status is Status.PERMITTED
    assert SHARING_ARGUMENT in found.detail
    assert "Drop the argument" in found.remedy


@pytest.mark.parametrize(
    "passthrough",
    [
        ("--no-share",),
        ("run", f"what does {SHARING_ARGUMENT} do?"),
        ("--shared-thing",),
    ],
    ids=["the opposite flag", "quoted in a prompt", "a longer flag"],
)
def test_an_argument_that_only_looks_like_it_is_not_read_as_asking(
    tmp_path, passthrough
):
    # Matched at the start of an argument rather than anywhere inside one. A
    # reading that took any of these for the flag would refuse every run that
    # mentions it, which is a tool nobody can ask about its own behaviour.
    assert _read(tmp_path, passthrough=passthrough).status is Status.DENIED


def test_a_file_that_is_not_an_object_says_so_rather_than_naming_a_missing_key(
    tmp_path,
):
    # `[]` states no keys because it cannot hold any, and telling somebody to
    # set one in it is advice they cannot follow. It parses, so nothing else
    # refuses it: `write_settings_where_nothing_is_kept` keeps any JSON.
    found = _read(tmp_path, body="[1, 2]")

    assert found.status is Status.UNWRITTEN
    assert "rather than an object" in found.detail
    assert "Replace it with an object" in found.remedy


def test_a_file_stating_the_key_as_nothing_is_not_called_a_file_without_it(tmp_path):
    # `null` is a value somebody wrote. Saying the file states no `share`
    # sends them looking for something that is in front of them.
    found = _read(tmp_path, body='{"share": null}')

    assert found.status is Status.PERMITTED
    assert "null" in found.detail


def test_a_file_that_is_not_json_is_a_fault_rather_than_an_answer(tmp_path):
    # Nothing about sharing can be read out of it, and guessing would be the
    # silent failure this reading exists to end.
    with pytest.raises(AgentSettingsError, match="not readable as JSON"):
        _read(tmp_path, body='{"share": ')
