import pytest

from offgrid.naming import parameter_counts

BILLION = 1e9


@pytest.mark.parametrize(
    ("identifier", "total", "active"),
    [
        # Qwen states active parameters after the total: 35B with 3B active.
        ("qwen/qwen3.6-35b-a3b", 35 * BILLION, 3 * BILLION),
        ("qwen3.6-35b-a3b-mlx@8bit", 35 * BILLION, 3 * BILLION),
        ("mlx-community/Qwen3.6-35B-A3B-MLX-4bit", 35 * BILLION, 3 * BILLION),
        # Dense models state one number.
        ("qwen/qwen3.6-27b", 27 * BILLION, None),
        ("meta/llama-3.1-8b", 8 * BILLION, None),
        ("mistral-7b-v0.3", 7 * BILLION, None),
        # Gemma states effective parameters, which is what has to be held.
        ("google/gemma-4-e4b", 4 * BILLION, None),
        # Fractions appear in small models.
        ("qwen/qwen2.5-1.5b", 1.5 * BILLION, None),
    ],
)
def test_sizes_are_read_from_the_identifier(
    identifier: str, total: float, active: float | None
):
    assert parameter_counts(identifier) == (total, active)


@pytest.mark.parametrize(
    "identifier",
    [
        "text-embedding-nomic-embed-text-v1.5",
        "some-publisher/a-model-with-no-size",
        "",
    ],
)
def test_an_identifier_without_a_size_reads_as_unknown(identifier: str):
    assert parameter_counts(identifier) == (None, None)


@pytest.mark.parametrize(
    "identifier",
    ["publisher/some-model-4bit", "publisher/some-model-8bit", "a-model@4bit"],
)
def test_a_quantization_is_not_mistaken_for_a_size(identifier: str):
    assert parameter_counts(identifier) == (None, None)


def test_a_version_number_is_not_mistaken_for_a_size():
    # qwen3.6 and llama-3.1 must not be read as 3.6B and 3.1B.
    assert parameter_counts("qwen/qwen3.6-35b-a3b")[0] == 35 * BILLION
    assert parameter_counts("meta/llama-3.1-8b")[0] == 8 * BILLION


def test_active_parameters_never_exceed_the_total():
    total, active = parameter_counts("qwen/qwen3.6-35b-a3b")
    assert total is not None and active is not None
    assert active < total
