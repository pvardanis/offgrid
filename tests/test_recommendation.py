"""What a recommendation reads as when the picker lays it out in columns.

The command line's fuller table keeps its own seam in `test_cli.py`. This is
the shape the machine panel shows: five columns per model and a one-line
caption, built from the same shortlist so the two surfaces cannot disagree
about what fits.
"""

from offgrid.domain.sizing.listing import Listing, Table
from offgrid.domain.sizing.machine import Machine
from offgrid.domain.sizing.recommendation import (
    PANEL_COLUMNS,
    recommend_for_the_panel,
)

GIB = 1024**3
BILLION = 1e9


def machine() -> Machine:
    """A machine with room for everything the tables below publish."""
    return Machine(
        chip="Apple M2 Max", memory_bytes=64 * GIB, wired_limit_bytes=48 * GIB
    )


def a_listing(
    name: str = "A-Model-30B",
    parameters: float = 30 * BILLION,
    active: float | None = None,
    coding_score: float | None = 77.2,
    context_window: int | None = 262144,
) -> Listing:
    """One published model, dense unless an active count is given."""
    return Listing(
        name=name,
        parameters=parameters,
        active_parameters=active,
        coding_score=coding_score,
        context_window=context_window,
        license="Apache 2.0",
    )


def a_table(*listings: Listing, unsized_rows: int = 0) -> Table:
    """A published list carrying these listings."""
    return Table(
        source="https://onyx.app/best-llm-for-coding",
        benchmark="swe_bench_verified",
        dated="2026-09-01",
        listings=list(listings),
        unsized_rows=unsized_rows,
    )


def test_the_panel_has_the_five_columns_the_spec_names():
    # model, params, quant, quality, and context — the reduced set the panel
    # shows, not the fuller table the command line prints.
    assert PANEL_COLUMNS == ("model", "params", "quant", "quality", "context")


def test_a_dense_model_states_its_size_without_an_active_count():
    recommendation = recommend_for_the_panel(a_table(a_listing()), machine())

    top = recommendation.models[0]

    assert top.name == "A-Model-30B"
    assert top.params == "30B"


def test_a_mixture_names_the_count_a_token_reads():
    # A model that routes each token to a fraction of itself says both what it
    # holds and what it reads, so a person sizes the run by the smaller number.
    listing = a_listing(name="qwen3-coder-30b-a3b", active=3 * BILLION)

    recommendation = recommend_for_the_panel(a_table(listing), machine())

    assert recommendation.models[0].params == "30B (3B active)"


def test_the_quality_column_carries_the_word_and_the_score():
    top = recommend_for_the_panel(a_table(a_listing()), machine()).models[0]

    label, separator, score = top.quality.partition(" · ")

    assert label
    assert separator == " · "
    assert score.isdigit()


def test_the_quant_and_context_are_the_widths_and_the_ceiling():
    top = recommend_for_the_panel(a_table(a_listing()), machine()).models[0]

    assert top.quant == "4-bit"
    assert top.context == "262144"


def test_a_listing_serving_nothing_states_no_context_rather_than_a_zero():
    listing = a_listing(context_window=None)

    top = recommend_for_the_panel(a_table(listing), machine()).models[0]

    assert top.context == "unstated"


def test_the_caption_names_the_list_the_figures_came_from():
    caption = recommend_for_the_panel(a_table(a_listing()), machine()).caption

    assert "onyx" in caption


def test_the_caption_counts_what_each_rule_dropped():
    # A row the list published no size for cannot be sized, and a row it scored
    # at nothing cannot be ranked. The caption accounts for both, so a model a
    # person expected and did not find is explainable.
    scored_but_unsized = 2
    table = a_table(
        a_listing(),
        a_listing(name="A-Closed-Model", coding_score=None),
        unsized_rows=scored_but_unsized,
    )

    caption = recommend_for_the_panel(table, machine()).caption

    assert "dropped 3" in caption
    assert "no size" in caption
    assert "no score" in caption


def test_nothing_dropped_is_left_off_the_caption():
    caption = recommend_for_the_panel(a_table(a_listing()), machine()).caption

    assert "dropped" not in caption
