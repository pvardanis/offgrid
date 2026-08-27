"""What every adapter says about having a model downloaded into it.

Asked of the registry rather than of a connection: how a model is downloaded
is a fact about a runtime, and no adapter is given an address to answer it.
That is what lets `recommend` print it beside names off a published list,
about models the runtime has never been asked about.

Nothing here stands a server in, and it does not have to: `conftest.py`
refuses the transport, so an adapter that reached for one would fail here
rather than answer.
"""

import pytest

from offgrid.domain.running.runtime import RuntimeName
from offgrid.runtimes import MODEL_DOWNLOAD_INSTRUCTIONS, describe_model_download
from offgrid.shared.wording import LINE_WIDTH

MODEL = "Qwen3.6-35B-A3B"


@pytest.mark.parametrize("runtime_name", list(RuntimeName), ids=lambda one: one.value)
def test_every_runtime_offgrid_names_says_how_a_model_is_downloaded(
    runtime_name: RuntimeName,
):
    # A name a profile may hold and nothing to say about it is an adapter
    # half registered: `recommend` would raise on a profile offgrid accepts.
    assert runtime_name in MODEL_DOWNLOAD_INSTRUCTIONS


@pytest.mark.parametrize("runtime_name", list(RuntimeName), ids=lambda one: one.value)
def test_how_a_model_is_downloaded_names_the_model(runtime_name: RuntimeName):
    # A sentence about downloading in general tells whoever is reading a list
    # of names nothing they do not already have.
    assert MODEL in describe_model_download(runtime_name, MODEL)


@pytest.mark.parametrize("runtime_name", list(RuntimeName), ids=lambda one: one.value)
def test_how_a_model_is_downloaded_is_said_in_lines_that_fit_a_terminal(
    runtime_name: RuntimeName,
):
    # Nothing reflows it — a command in it has to survive being copied — so
    # where the lines fall is the adapter's, and this is what it owes for
    # them: a line that wraps under the table it sits below is one an adapter
    # wrote too long.
    said = describe_model_download(runtime_name, MODEL)

    assert said.splitlines()
    for line in said.splitlines():
        assert len(line) <= LINE_WIDTH, line
