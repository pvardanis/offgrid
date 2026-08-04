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


def test_a_profile_can_name_the_model_to_use(tmp_path):
    path = tmp_path / "profile.yaml"
    save(
        Profile.describing(
            a_machine(), host="127.0.0.1:1234", model="qwen/qwen3.6-35b-a3b"
        ),
        path,
    )

    assert load(path).model == "qwen/qwen3.6-35b-a3b"


def test_a_profile_written_before_models_were_named_still_loads(tmp_path):
    # Exactly what `offgrid setup` wrote before this key existed.
    path = tmp_path / "profile.yaml"
    path.write_text(
        "host: 127.0.0.1:1234\n"
        "runtime: lmstudio\n"
        "agent: claude-code\n"
        "chip: Apple M1 Max\n"
        "memory_bytes: 68719476736\n"
        "wired_limit_bytes: 60129542144\n"
    )

    assert load(path).model is None
