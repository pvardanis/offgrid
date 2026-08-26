"""What the profile file itself does, either side of what it says.

The README advertises the file as hand-editable, so a save answers for the
comments, the blank lines and the key order that were already there, and a
read answers for a key somebody typed twice. What a profile has to say to
load is in `test_profile.py`.
"""

import pytest

from offgrid.cli.binding import read_profile
from offgrid.domain.profile import save_profile
from offgrid.domain.running.model import ModelRequest
from offgrid.shared.exceptions import ProfileError
from tests.profiles import HOST, build_profile

NAMED_MODEL = "qwen/qwen3.6-35b-a3b"

# A file as somebody keeps one: a note above each section, a blank line between
# them, and the name written before the address rather than after it.
HAND_EDITED = f"""\
# The runtime this machine talks to.
runtime:
  name: lmstudio
  host: 127.0.0.1:1234

agent:
  name: claude-code  # what `offgrid run` starts

# Held at a window this machine has room for.
model:
  identifier: {NAMED_MODEL}
  context_window: 32768
"""

# The whole of a profile typed from the README, which names no model at all.
TYPED_BY_HAND = """\
# Where the runtime listens.
runtime:
  name: lmstudio
  host: 127.0.0.1:1234
agent:
  name: claude-code
"""


def test_a_hand_edited_profile_survives_being_written_back(tmp_path):
    # A save that reformatted the file would make the promise that it can be
    # edited conditional on never saving it.
    path = tmp_path / "profile.yaml"
    path.write_text(HAND_EDITED)

    save_profile(read_profile(path), path)

    assert path.read_text() == HAND_EDITED


def test_changing_one_value_leaves_the_rest_of_the_file_alone(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text(HAND_EDITED)
    stored = read_profile(path)

    save_profile(
        stored.model_copy(
            update={"model": ModelRequest(identifier=NAMED_MODEL, context_window=65536)}
        ),
        path,
    )

    written = path.read_text()
    assert "context_window: 65536" in written
    assert written.replace("65536", "32768") == HAND_EDITED


def test_a_key_the_file_never_named_is_written_after_what_is_there(tmp_path):
    # A profile typed by hand has nowhere for a model to go. The section is
    # added where the next key would be typed, rather than by rewriting.
    path = tmp_path / "profile.yaml"
    path.write_text(TYPED_BY_HAND)

    save_profile(read_profile(path), path)

    written = path.read_text()
    assert written.startswith(TYPED_BY_HAND)
    assert written[len(TYPED_BY_HAND) :] == "model:\n  identifier:\n  context_window:\n"


def test_a_file_holding_a_key_offgrid_cannot_act_on_is_written_whole(tmp_path):
    # `setup` writes over a profile it refused, and a measured machine left in
    # the file would be refused all over again by the next read. Nothing around
    # it is kept either: a comment stands above the key it is about, and one
    # left behind would say something false about whatever followed it.
    path = tmp_path / "profile.yaml"
    path.write_text(HAND_EDITED + "# What this machine measured.\nchip: Apple M1\n")

    save_profile(build_profile(), path)

    written = path.read_text()
    assert "chip" not in written
    assert "#" not in written
    assert read_profile(path).runtime.host == HOST


def test_a_key_typed_twice_is_refused_rather_than_read_as_the_last_one(tmp_path):
    # A profile is hand-edited, and a key that is there twice is a mistake to
    # report: reading the second and dropping the first answers with a value
    # nobody meant, from a file that says both.
    path = tmp_path / "profile.yaml"
    path.write_text(f"runtime:\n  name: lmstudio\n  host: {HOST}\n  host: 10.0.0.5:1\n")

    with pytest.raises(ProfileError, match="duplicate key"):
        read_profile(path)


def test_a_profile_written_where_there_is_none_is_written_whole(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text(HAND_EDITED)
    stored = read_profile(path)

    save_profile(stored, tmp_path / "fresh.yaml")

    assert (tmp_path / "fresh.yaml").read_text() == (
        "runtime:\n  host: 127.0.0.1:1234\n  name: lmstudio\n"
        "agent:\n  name: claude-code\n"
        f"model:\n  identifier: {NAMED_MODEL}\n  context_window: 32768\n"
    )
