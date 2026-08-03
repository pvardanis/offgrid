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
        # Fractions appear in small models, written either way.
        ("qwen/qwen2.5-1.5b", 1.5 * BILLION, None),
        ("stabilityai/stablelm-2-1_6b", 1.6 * BILLION, None),
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


@pytest.mark.parametrize(
    "identifier",
    [
        # A version fused to a "b" is a version, not a size.
        "publisher/qwen3.6b-instruct",
        "publisher/llama3b-chat",
        # Mixtral counts experts, not parameters: 8x7B holds 46.7 billion, so
        # reading 7 would undersize it sevenfold.
        "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "mistralai/Mixtral-8x22B-v0.1",
    ],
)
def test_a_size_must_be_introduced_by_a_separator(identifier: str):
    assert parameter_counts(identifier) == (None, None)


def test_a_version_number_before_a_real_size_is_ignored():
    assert parameter_counts("qwen/qwen3.6-35b-a3b")[0] == 35 * BILLION
    assert parameter_counts("meta/llama-3.1-8b")[0] == 8 * BILLION


def test_an_active_count_without_a_total_is_not_half_known():
    # Qwen1.5-MoE-A2.7B names what is active but never the total, and a model
    # that cannot be sized must not report a speed either.
    assert parameter_counts("Qwen/Qwen1.5-MoE-A2.7B") == (None, None)
