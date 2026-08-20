"""What a profile says about the model to run, and at what window.

The section belongs to neither adapter: the agent sets the floor, the runtime
honours the number and the model states the ceiling. What the rest of the file
does is in `test_profile.py`.
"""

import pytest

from offgrid.binding import read_profile
from offgrid.domain.profile import save_profile
from offgrid.domain.running.model import ModelRequest
from offgrid.shared.exceptions import ProfileError
from tests.profiles import HOST, NAMED, build_profile

WANTED = "qwen/qwen3.6-35b-a3b"


def _typed(tmp_path, said: str):
    """Write a profile with a `model` section typed into it by hand."""
    path = tmp_path / "profile.yaml"
    path.write_text(NAMED.format(host=HOST) + said)

    return path


def test_a_profile_can_name_the_model_to_use(tmp_path):
    path = tmp_path / "profile.yaml"
    save_profile(build_profile(model=ModelRequest(identifier=WANTED)), path)

    assert read_profile(path).model == ModelRequest(identifier=WANTED)


def test_a_profile_can_ask_for_a_model_at_a_window(tmp_path):
    # The two things that say what to run sit together, so a window written
    # once is asked for by every run without anyone typing it.
    path = _typed(
        tmp_path, f"model:\n  identifier: {WANTED}\n  context_window: 32768\n"
    )

    assert read_profile(path).model == ModelRequest(
        identifier=WANTED, context_window=32768
    )


def test_a_model_named_without_a_window_inherits_the_one_being_served(tmp_path):
    # Naming no window is a statement: whatever the runtime remembers stands,
    # which is what every profile written before the section said.
    path = _typed(tmp_path, f"model:\n  identifier: {WANTED}\n")

    assert read_profile(path).model == ModelRequest(
        identifier=WANTED, context_window=None
    )


def test_a_window_can_be_asked_for_without_naming_a_model(tmp_path):
    # A window with no model is the resident one held at that window, the
    # same statement `--context-window` alone makes.
    path = _typed(tmp_path, "model:\n  context_window: 32768\n")

    assert read_profile(path).model == ModelRequest(
        identifier=None, context_window=32768
    )


def test_a_profile_with_no_model_section_runs_against_what_is_resident(tmp_path):
    path = _typed(tmp_path, "")

    assert read_profile(path).model is None


def test_a_model_written_as_a_name_is_refused_with_the_shape_to_write(tmp_path):
    # The shape every profile written before the section is in. Naming the
    # key alone leaves the reader guessing at what replaces it.
    path = _typed(tmp_path, f"model: {WANTED}\n")

    with pytest.raises(ProfileError) as refused:
        read_profile(path)

    said = str(refused.value)
    assert "profile.yaml" in said
    assert f"model:\n  identifier: {WANTED}" in said
    assert "context_window" in said


def test_a_mistyped_key_inside_the_section_is_refused_rather_than_dropped(tmp_path):
    # `context_windwo:` read as "no window wanted" runs at whatever the
    # runtime remembered, while the person believes they asked for 32768.
    path = _typed(
        tmp_path, f"model:\n  identifier: {WANTED}\n  context_windwo: 32768\n"
    )

    with pytest.raises(ProfileError) as refused:
        read_profile(path)

    assert "context_windwo" in str(refused.value)


def test_a_model_named_as_nothing_is_refused_rather_than_read_as_unnamed(tmp_path):
    # `identifier: ""` is a name nobody typed, not the absence of one. Read as
    # absence it answers with whatever is resident, where the runtime should
    # have said it does not have that.
    path = _typed(tmp_path, 'model:\n  identifier: ""\n')

    with pytest.raises(ProfileError) as refused:
        read_profile(path)

    assert "identifier" in str(refused.value)


def test_a_window_of_nothing_is_refused_as_not_a_window(tmp_path):
    # Zero is not a small window. Typer refuses it on the command line, and
    # the profile is the other door to the same request.
    path = _typed(tmp_path, "model:\n  context_window: 0\n")

    with pytest.raises(ProfileError) as refused:
        read_profile(path)

    assert "context_window" in str(refused.value)
