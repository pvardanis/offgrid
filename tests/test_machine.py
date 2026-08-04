import platform

import pytest

from offgrid.exceptions import UnsupportedMachineError
from offgrid.machine import detect, parse, require_apple_silicon

GIB = 1024**3

# Captured from an M1 Max running macOS 24.6.0.
BRAND = "Apple M1 Max"
MEMSIZE = "68719476736"
WIRED_MB = "57344"


def test_parse_reads_the_chip_and_memory():
    parsed = parse(BRAND, MEMSIZE, WIRED_MB)
    assert parsed.chip == "Apple M1 Max"
    assert parsed.memory_bytes == 64 * GIB


def test_parse_converts_the_wired_limit_from_megabytes():
    assert parse(BRAND, MEMSIZE, WIRED_MB).wired_limit_bytes == 57344 * 1024 * 1024


def test_an_unset_wired_limit_reads_as_zero_and_becomes_none():
    assert parse(BRAND, MEMSIZE, "0").wired_limit_bytes is None


def test_a_missing_wired_limit_becomes_none():
    assert parse(BRAND, MEMSIZE, None).wired_limit_bytes is None


def test_a_wired_limit_above_physical_memory_cannot_conjure_memory():
    # iogpu.wired_limit_mb takes any value the user types, including a typo.
    absurd = parse(BRAND, str(16 * GIB), str(512 * 1024))
    assert absurd.usable_bytes == 16 * GIB


def test_the_default_share_leaves_most_of_the_machine_usable():
    # Guards the constant from below: shrinking it would refuse models that fit.
    assert parse(BRAND, MEMSIZE, "0").usable_bytes == pytest.approx(48 * GIB)


def test_a_machine_reporting_no_memory_is_refused():
    with pytest.raises(UnsupportedMachineError, match="memory"):
        parse(BRAND, "0", None)


def test_unreadable_memory_is_refused_rather_than_guessed():
    with pytest.raises(UnsupportedMachineError, match=r"hw\.memsize"):
        parse(BRAND, "not-a-number", None)


def test_intel_macs_are_refused():
    with pytest.raises(UnsupportedMachineError, match="Apple Silicon"):
        require_apple_silicon("Darwin", "x86_64")


def test_linux_is_refused():
    with pytest.raises(UnsupportedMachineError, match="macOS"):
        require_apple_silicon("Linux", "aarch64")


def test_apple_silicon_macs_are_accepted():
    require_apple_silicon("Darwin", "arm64")


@pytest.mark.skipif(
    platform.system() != "Darwin" or platform.machine() != "arm64",
    reason="reads this machine's sysctl values",
)
def test_detect_reads_this_machine():
    here = detect()
    assert here.chip.startswith("Apple ")
    assert here.memory_bytes >= 8 * GIB
    assert here.usable_bytes <= here.memory_bytes
