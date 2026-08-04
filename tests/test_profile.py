import pytest
import yaml

from offgrid.exceptions import ProfileError
from offgrid.machine import Machine
from offgrid.profile import Profile, load, save

GIB = 1024**3


def a_machine() -> Machine:
    return Machine(
        chip="Apple M1 Max", memory_bytes=64 * GIB, wired_limit_bytes=56 * GIB
    )


def test_a_saved_profile_reads_back_the_same(tmp_path):
    path = tmp_path / "profile.yaml"
    written = Profile.describing(a_machine(), host="127.0.0.1:1234")
    save(written, path)

    assert load(path) == written


def test_a_profile_is_readable_yaml(tmp_path):
    path = tmp_path / "profile.yaml"
    save(Profile.describing(a_machine(), host="127.0.0.1:1234"), path)

    on_disk = yaml.safe_load(path.read_text())
    assert on_disk["host"] == "127.0.0.1:1234"
    assert on_disk["chip"] == "Apple M1 Max"


def test_a_missing_profile_says_how_to_make_one(tmp_path):
    with pytest.raises(ProfileError, match="offgrid setup"):
        load(tmp_path / "absent.yaml")


def test_a_profile_that_is_not_a_mapping_is_refused(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text("just a string\n")

    with pytest.raises(ProfileError, match="not a profile"):
        load(path)


def test_a_profile_missing_a_field_names_the_field(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.safe_dump({"host": "127.0.0.1:1234"}))

    with pytest.raises(ProfileError, match="chip"):
        load(path)


def test_the_machine_is_recorded_as_measured(tmp_path):
    profile = Profile.describing(a_machine(), host="127.0.0.1:1234")

    assert profile.memory_bytes == 64 * GIB
    assert profile.wired_limit_bytes == 56 * GIB
