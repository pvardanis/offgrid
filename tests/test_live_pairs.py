"""What a run does for each pair of runtime and agent on this machine.

Opt-in, with `uv run pytest -m live`. A run holds a model, starts the agent
against it and lets the model go, and that sentence is the same for both
agents — so this is parameterised over them rather than written twice.

It is the only place the OpenAI path is exercised end to end: everything else
about that pair is proven against doubles and payloads captured from a live
server, which cannot say whether a real turn answers.

Both agents have to be installed, and a machine missing one is told which
binary and where to get it.
"""

import pytest

from offgrid.cli.binding import read_profile
from offgrid.domain.profile import DEFAULT_PATH
from offgrid.runtimes.lmstudio.catalogue import (
    get_catalogue_payload,
    get_held_instances,
)
from tests.live_pairs import get_one_shot_args
from tests.live_runs import REFUSALS, STATED_WINDOW, run_offgrid

pytestmark = pytest.mark.live


def test_a_run_of_a_pair_holds_the_model_and_lets_it_go(
    host: str, known: str, paired: str
):
    # Nothing offgrid prints names the agent, so what the run will read is
    # what says which pair this is: a run reads the stored profile, and the
    # profile is the only place the agent is named.
    assert read_profile(DEFAULT_PATH).agent.name.value == paired

    # Not that the agent liked the answer: a model this small answers with
    # whatever it can, and that is its business. What offgrid owes is that the
    # agent started against the model it held, and that the memory came back.
    finished = run_offgrid(known, get_one_shot_args(paired), window=STATED_WINDOW)

    assert finished.returncode not in REFUSALS, finished.stderr
    # Exit codes alone cannot tell a run that held a model from one that
    # never reached the runtime — a usage error exits 2 and leaves nothing
    # loaded, which would satisfy the rest of this on its own.
    assert known in finished.stderr
    # The agent prints what the model said, so an empty one is a run that
    # started and never got an answer out of the provider it was pointed at.
    assert finished.stdout.strip(), finished.stderr
    assert get_held_instances(get_catalogue_payload(host), known) == [], finished.stderr
