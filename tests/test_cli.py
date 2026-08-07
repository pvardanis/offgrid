import logging
import pathlib

import pytest
from typer.testing import CliRunner

from offgrid.cli import app
from offgrid.machine import Machine

GIB = 1024**3
CEILING = 262144
RESIDENT = "qwen/qwen3.6-35b-a3b"
runner = CliRunner()


def _entry(identifier: str, *, served: int, ceiling: int, in_memory: bool) -> dict:
    """Describe one model the way LM Studio's catalogue does."""
    entry = {
        "id": identifier,
        "type": "llm",
        "state": "loaded" if in_memory else "not-loaded",
        "max_context_length": ceiling,
    }
    if in_memory:
        entry["loaded_context_length"] = served

    return entry


def _runtime(monkeypatch, *, holding=None, cold=None, ceiling=CEILING) -> dict:
    """Stand in for the model server, answering as what it holds changes.

    Each mapping is a model against the context it is served at. A cold model
    states only its ceiling until something loads it, which is what makes the
    difference between the two numbers visible.

    :return: What the runtime was asked to load and let go of.
    """
    served = {**(holding or {}), **(cold or {})}
    in_memory = dict.fromkeys(holding or {}, True) | dict.fromkeys(cold or {}, False)
    asked: dict = {"loaded": None, "let_go": [], "order": []}

    def catalogue(host: str) -> dict:
        return {
            "data": [
                _entry(name, served=served[name], ceiling=ceiling, in_memory=held)
                for name, held in in_memory.items()
            ]
        }

    def load(host: str, identifier: str, **kwargs) -> None:
        in_memory[identifier] = True
        asked["loaded"] = identifier
        asked["order"].append(("loaded", identifier))

    def unload(host: str, identifier: str) -> None:
        in_memory[identifier] = False
        asked["let_go"].append(identifier)
        asked["order"].append(("let_go", identifier))

    monkeypatch.setattr("offgrid.hold.catalogue", catalogue)
    monkeypatch.setattr("offgrid.hold.load_model", load)
    monkeypatch.setattr("offgrid.hold.unload", unload)

    return asked


def _launched(monkeypatch, code: int = 0, order: list | None = None) -> dict:
    """Record what would have been started, without starting it.

    :param monkeypatch: The test's patcher.
    :param code: What the agent exits with.
    :param order: A record of what the runtime was asked, to place the launch
        among it.

    :return: The environment and command the agent would have had.
    """
    seen: dict = {}

    def start(launch) -> int:
        if order is not None:
            order.append(("started", launch.argv[0]))
        seen.update(env=launch.env, argv=launch.argv)

        return code

    monkeypatch.setattr("offgrid.cli.start", start)

    return seen


@pytest.fixture
def runtime(monkeypatch):
    """A model server holding one model, served below its ceiling."""
    return _runtime(monkeypatch, holding={RESIDENT: 212224})


@pytest.fixture
def here(monkeypatch, tmp_path, runtime):
    """Answer with a fixed machine, and write nowhere real."""
    machine = Machine(
        chip="Apple M1 Max", memory_bytes=64 * GIB, wired_limit_bytes=56 * GIB
    )
    monkeypatch.setattr("offgrid.cli.detect", lambda: machine)
    monkeypatch.setattr("offgrid.cli.DEFAULT_PATH", tmp_path / "profile.yaml")
    monkeypatch.setattr("offgrid.cli.CONFIG_DIR", tmp_path / "claude-code")
    return tmp_path


def test_setup_reports_the_machine(here):
    result = runner.invoke(app, ["setup"])
    assert result.exit_code == 0
    assert "Apple M1 Max" in result.stderr


def test_setup_says_what_size_of_model_fits(here):
    result = runner.invoke(app, ["setup"])
    assert "4-bit" in result.stderr
    assert "parameters" in result.stderr


def test_setup_names_no_model(here):
    # Choosing one is a manual step; offgrid states the budget, not the answer.
    result = runner.invoke(app, ["setup"])
    assert "qwen" not in result.stderr


def test_setup_writes_a_profile_that_can_be_read_back(here):
    from offgrid.profile import load

    runner.invoke(app, ["setup"])
    assert load(here / "profile.yaml").chip == "Apple M1 Max"


def test_setup_run_again_keeps_what_was_edited_by_hand(here):
    # `setup` invites a re-run: the sysctl advice it prints is undone by a
    # reboot. A re-run that wipes the model chosen since is a trap.
    runner.invoke(app, ["setup"])
    _name_in_profile(here, "a/chosen-by-hand-7b")

    result = runner.invoke(app, ["setup"])

    from offgrid.profile import load

    assert result.exit_code == 0
    assert load(here / "profile.yaml").model == "a/chosen-by-hand-7b"


def test_setup_keeps_the_profile_it_could_not_read(here):
    # It is about to write over a file someone edited by hand. Whatever was
    # in it is worth more than the seconds it takes to keep a copy.
    runner.invoke(app, ["setup"])
    (here / "profile.yaml").write_text("model: [unbalanced\n")

    result = runner.invoke(app, ["setup"])

    assert result.exit_code == 0
    assert (here / "profile.yaml.rejected").read_text() == "model: [unbalanced\n"
    assert "profile.yaml.rejected" in result.stderr


def test_setup_takes_the_host_it_is_given_over_the_stored_one(here):
    runner.invoke(app, ["setup", "--host", "10.0.0.5:4321"])
    runner.invoke(app, ["setup", "--host", "127.0.0.1:1234"])

    from offgrid.profile import load

    assert load(here / "profile.yaml").host == "127.0.0.1:1234"


def test_setup_keeps_a_host_that_was_stored_when_none_is_given(here):
    runner.invoke(app, ["setup", "--host", "10.0.0.5:4321"])
    runner.invoke(app, ["setup"])

    from offgrid.profile import load

    assert load(here / "profile.yaml").host == "10.0.0.5:4321"


def test_doctor_needs_a_profile_first(here):
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "offgrid setup" in result.stderr


def test_doctor_reports_the_model_that_would_answer(here):
    runner.invoke(app, ["setup"])
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert RESIDENT in result.stderr


def test_doctor_says_when_the_runtime_holds_nothing(here, monkeypatch):
    runner.invoke(app, ["setup"])
    _runtime(monkeypatch, cold={"a/cold-7b": 8192})

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "no model" in result.stderr.lower()


def test_run_launches_the_agent_with_the_resident_model(here, monkeypatch):
    runner.invoke(app, ["setup"])
    started = _launched(monkeypatch)

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    assert started["env"]["ANTHROPIC_MODEL"] == RESIDENT
    assert started["argv"][0] == "claude"


def test_run_passes_the_rest_of_the_line_to_the_agent(here, monkeypatch):
    runner.invoke(app, ["setup"])
    started = _launched(monkeypatch)

    runner.invoke(app, ["run", "--", "-p", "hello"])
    assert started["argv"][-2:] == ["-p", "hello"]


def test_run_refuses_when_nothing_is_loaded(here, monkeypatch):
    runner.invoke(app, ["setup"])
    _runtime(monkeypatch, cold={"a/cold-7b": 8192})

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 1
    assert "load a model" in result.stderr.lower()


def test_run_loads_a_named_model_that_is_not_resident(here, monkeypatch):
    runner.invoke(app, ["setup"])
    asked = _runtime(monkeypatch, holding={RESIDENT: 212224}, cold={"a/other-7b": 8192})
    _launched(monkeypatch)

    result = runner.invoke(app, ["run", "--model", "a/other-7b"])
    assert result.exit_code == 0
    assert asked["loaded"] == "a/other-7b"


def test_a_resident_model_is_not_loaded_again(here, monkeypatch, runtime):
    # Asking for what is already held costs nothing: no wait for weights, and
    # the prefix cached against it survives.
    runner.invoke(app, ["setup"])
    _launched(monkeypatch)

    result = runner.invoke(app, ["run", "--model", RESIDENT])
    assert result.exit_code == 0
    assert runtime["loaded"] is None


def test_swapping_models_says_what_it_costs(here, monkeypatch):
    runner.invoke(app, ["setup"])
    _runtime(monkeypatch, holding={RESIDENT: 212224}, cold={"a/other-7b": 8192})
    _launched(monkeypatch)

    result = runner.invoke(app, ["run", "--model", "a/other-7b"])
    assert result.exit_code == 0
    assert "cached prefix" in result.stderr


def test_a_model_the_runtime_does_not_have_is_refused(here, monkeypatch):
    runner.invoke(app, ["setup"])
    _launched(monkeypatch)

    result = runner.invoke(app, ["run", "--model", "a/absent-7b"])
    assert result.exit_code == 1
    assert "a/absent-7b" in result.stderr


def test_run_lets_go_of_models_it_did_not_ask_for(here, monkeypatch):
    runner.invoke(app, ["setup"])
    asked = _runtime(monkeypatch, holding={RESIDENT: 212224}, cold={"a/other-7b": 8192})
    _launched(monkeypatch)

    runner.invoke(app, ["run", "--model", "a/other-7b"])
    assert RESIDENT in asked["let_go"]


def test_every_model_held_is_let_go_not_only_the_first(here, monkeypatch):
    # LM Studio holds several at once. One left behind is memory nothing on
    # the machine can use for the whole session.
    runner.invoke(app, ["setup"])
    asked = _runtime(
        monkeypatch,
        holding={RESIDENT: 212224, "a/also-held-7b": 8192},
        cold={"a/other-7b": 8192},
    )
    _launched(monkeypatch)

    runner.invoke(app, ["run", "-m", "a/other-7b"])
    assert asked["let_go"][:2] == [RESIDENT, "a/also-held-7b"]


def test_a_model_already_held_is_not_let_go_of_and_loaded_again(here, monkeypatch):
    # `resident` answers with the first model in catalogue order, so a
    # wanted model that is held but not first is one `continue` away from
    # being evicted and reloaded — the whole wait, for no change.
    runner.invoke(app, ["setup"])
    asked = _runtime(monkeypatch, holding={RESIDENT: 212224, "a/wanted-7b": 8192})
    _launched(monkeypatch)

    runner.invoke(app, ["run", "-m", "a/wanted-7b"])
    assert asked["loaded"] is None
    assert "a/wanted-7b" not in asked["let_go"][:1]


def test_the_model_is_held_only_for_as_long_as_the_agent_runs(here, monkeypatch):
    # What is already held goes first, the wanted model is loaded next, and
    # it is let go after the agent and not before it.
    runner.invoke(app, ["setup"])
    asked = _runtime(monkeypatch, holding={RESIDENT: 212224}, cold={"a/other-7b": 8192})
    _launched(monkeypatch, order=asked["order"])

    runner.invoke(app, ["run", "-m", "a/other-7b"])
    assert asked["order"] == [
        ("let_go", RESIDENT),
        ("loaded", "a/other-7b"),
        ("started", "claude"),
        ("let_go", "a/other-7b"),
    ]


def test_an_agent_that_cannot_talk_to_the_runtime_is_refused_before_the_wait(
    here, monkeypatch
):
    # Checking after the load spends a minute of someone's time to arrive at
    # an answer that was knowable before it started.
    from offgrid.dialect import Dialect

    runner.invoke(app, ["setup"])
    asked = _runtime(monkeypatch, cold={"a/other-7b": 8192})
    _launched(monkeypatch)
    monkeypatch.setattr("offgrid.cli.agent_dialect", lambda: Dialect.OPENAI)

    result = runner.invoke(app, ["run", "-m", "a/other-7b"])
    assert result.exit_code == 1
    assert "translat" in result.stderr
    assert asked["order"] == []


def test_the_model_is_let_go_when_the_agent_finishes(here, monkeypatch, runtime):
    runner.invoke(app, ["setup"])
    _launched(monkeypatch)

    runner.invoke(app, ["run"])
    assert runtime["let_go"][-1] == RESIDENT


def test_the_agents_exit_code_is_offgrids_own(here, monkeypatch):
    runner.invoke(app, ["setup"])
    _launched(monkeypatch, code=3)

    assert runner.invoke(app, ["run"]).exit_code == 3


def test_the_model_is_let_go_even_when_the_agent_is_interrupted(
    here, monkeypatch, runtime
):
    runner.invoke(app, ["setup"])

    def interrupted(launch):
        raise KeyboardInterrupt

    monkeypatch.setattr("offgrid.cli.start", interrupted)

    runner.invoke(app, ["run"])
    assert runtime["let_go"] == [RESIDENT]


def test_settings_that_would_let_the_agent_search_stop_the_run(here, monkeypatch):
    runner.invoke(app, ["setup"])
    asked = _runtime(monkeypatch, cold={"a/other-7b": 8192})
    _launched(monkeypatch)
    config = here / "claude-code"
    config.mkdir()
    (config / "settings.json").write_text('{"theme": "mine"}')

    result = runner.invoke(app, ["run", "-m", "a/other-7b"])
    assert result.exit_code == 1
    assert "WebSearch" in result.stderr
    assert asked["order"] == []


def test_the_model_is_let_go_when_the_launch_cannot_be_built(
    here, monkeypatch, runtime
):
    # Between holding a model and starting the agent there is nothing a
    # person waits for, but it is the second after the longest wait in the
    # program, which is when a hand reaches for Ctrl-C.
    runner.invoke(app, ["setup"])

    def broken(*args, **kwargs):
        raise RuntimeError("the launch could not be built")

    monkeypatch.setattr("offgrid.cli.plan", broken)

    runner.invoke(app, ["run"])
    assert runtime["let_go"] == [RESIDENT]


def test_the_model_is_let_go_when_the_agent_will_not_start(here, monkeypatch, runtime):
    # A model held for an agent that never ran is memory nothing is using,
    # and it stays held for the rest of the session.
    runner.invoke(app, ["setup"])

    def missing(launch):
        raise FileNotFoundError(2, "No such file or directory", "claude")

    monkeypatch.setattr("offgrid.cli.start", missing)

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 127
    assert "claude" in result.stderr
    assert "on PATH" in result.stderr
    assert runtime["let_go"] == [RESIDENT]


def test_an_agent_that_is_there_but_not_executable_is_not_called_missing(
    here, monkeypatch, runtime
):
    # "Install it, or put it on PATH" sends someone to check a PATH that is
    # already right, for a file that is already there.
    runner.invoke(app, ["setup"])

    def denied(launch):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr("offgrid.cli.start", denied)

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 127
    assert "not executable" in result.stderr
    assert "on PATH" not in result.stderr


def test_a_runtime_that_will_not_let_go_is_reported_not_hidden(here, monkeypatch):
    from offgrid.exceptions import RuntimeUnreachableError

    runner.invoke(app, ["setup"])

    def refuse(host, name):
        raise RuntimeUnreachableError("lms would not unload it")

    monkeypatch.setattr("offgrid.hold.unload", refuse)
    _launched(monkeypatch)

    result = runner.invoke(app, ["run"])
    assert "still holding" in result.stderr


def test_the_profile_names_the_model_when_the_command_line_does_not(here, monkeypatch):
    runner.invoke(app, ["setup"])
    _name_in_profile(here, "a/other-7b")
    asked = _runtime(monkeypatch, holding={RESIDENT: 212224}, cold={"a/other-7b": 8192})
    _launched(monkeypatch)

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    assert asked["loaded"] == "a/other-7b"


def test_compaction_is_sized_from_what_the_runtime_serves(here, monkeypatch):
    # A model that was not loaded yet states only its ceiling. LM Studio
    # serves a smaller window than that, and compacting against the ceiling
    # means never compacting: the server truncates the prefix instead.
    runner.invoke(app, ["setup"])
    _runtime(monkeypatch, cold={"a/big-7b": 32768}, ceiling=262144)
    started = _launched(monkeypatch)

    runner.invoke(app, ["run", "-m", "a/big-7b"])
    assert started["env"]["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] == "32768"


def test_the_command_line_beats_the_profile(here, monkeypatch):
    runner.invoke(app, ["setup"])
    _name_in_profile(here, "a/from-profile-7b")
    asked = _runtime(
        monkeypatch, cold={"a/from-profile-7b": 8192, "a/asked-for-7b": 8192}
    )
    started = _launched(monkeypatch)

    runner.invoke(app, ["run", "-m", "a/asked-for-7b"])
    assert asked["loaded"] == "a/asked-for-7b"
    assert started["env"]["ANTHROPIC_MODEL"] == "a/asked-for-7b"


def test_saying_something_after_a_command_does_not_write_to_a_closed_stream(
    here, capsys
):
    # A handler that captured the stream a command ran on writes into a
    # closed buffer once that command is over, and logging reports that as a
    # traceback over whatever is being read at the time.
    runner.invoke(app, ["setup"])
    capsys.readouterr()

    logging.getLogger("offgrid.hold").info("something after the fact")

    assert "Logging error" not in capsys.readouterr().err


def test_an_error_that_reaches_the_terminal_is_a_sentence_not_a_traceback(
    monkeypatch, capsys
):
    from offgrid.cli import main
    from offgrid.exceptions import RuntimeUnreachableError

    def gone():
        raise RuntimeUnreachableError("the runtime went away mid-run")

    monkeypatch.setattr("offgrid.cli.app", gone)

    with pytest.raises(SystemExit) as raised:
        main()

    assert raised.value.code == 1
    assert "the runtime went away mid-run" in capsys.readouterr().err


def _name_in_profile(here, identifier: str) -> None:
    """Write a model into the stored profile, as a person editing it would."""
    path = here / "profile.yaml"
    path.write_text(path.read_text() + f"model: {identifier}\n")


def _listed(
    name: str,
    parameters: str | None,
    context: int = 262144,
    score: float | None = 70.0,
    active: str | None = None,
) -> dict:
    """Describe one model the way the published table does."""
    return {
        "name": name,
        "parameters": parameters,
        "activeParameters": active or parameters,
        "contextWindow": context,
        "benchmarks": {"swe_bench_verified": score},
        "operational": {"vram_int4": 18, "license": "Apache 2.0"},
    }


def _leaderboard(monkeypatch, *, models: list[dict], dated: str = "2026-07-20") -> None:
    """Answer for the published table, without reaching for it.

    The payload is the page's own React flight text, so what is served here
    is the shape that carries it: compact JSON with the table under the prop
    name the parser locates.
    """
    import json

    flight = '0:["$","div",null,' + json.dumps(
        {"config": {"lastUpdated": dated, "models": models}}, separators=(",", ":")
    )

    monkeypatch.setattr("offgrid.cli.fetch", lambda: flight)


def test_recommend_lists_a_model_once_for_each_width_it_fits_at(here, monkeypatch):
    _leaderboard(
        monkeypatch,
        models=[_listed("A-Model-35B", "35B"), _listed("A-Model-400B", "400B")],
    )

    result = runner.invoke(app, ["recommend"])
    rows = [line for line in result.stderr.splitlines() if "A-Model-35B" in line]

    assert result.exit_code == 0
    assert len(rows) == 2
    assert "4-bit" in rows[0]
    assert "8-bit" in rows[1]
    assert "A-Model-400B" not in result.stderr


def test_recommend_states_the_size_width_context_and_licence_of_each_row(
    here, monkeypatch
):
    _leaderboard(monkeypatch, models=[_listed("A-Model-35B", "35B", context=131072)])

    result = runner.invoke(app, ["recommend"])
    row = next(line for line in result.stderr.splitlines() if "A-Model-35B" in line)

    assert "17.5GB" in row
    assert "4-bit" in row
    assert "131072" in row
    assert "Apache 2.0" in row


def test_recommend_states_the_date_the_table_gives_itself(here, monkeypatch):
    # A table is worth reading if it is recent, and only the table knows.
    _leaderboard(
        monkeypatch, models=[_listed("A-Model-35B", "35B")], dated="2026-07-20"
    )

    result = runner.invoke(app, ["recommend"])

    assert "2026-07-20" in result.stderr


def test_recommend_leaves_out_a_model_published_with_no_size(here, monkeypatch):
    # Every closed model on the table is dropped by this rule alone, and no
    # licence is read to do it.
    _leaderboard(
        monkeypatch,
        models=[_listed("A-Closed-Model", None), _listed("A-Model-35B", "35B")],
    )

    result = runner.invoke(app, ["recommend"])

    assert "A-Closed-Model" not in result.stderr
    assert "A-Model-35B" in result.stderr


def test_recommend_caps_nothing(here, monkeypatch):
    _leaderboard(
        monkeypatch,
        models=[_listed(f"A-Model-{n}", "7B") for n in range(12)],
    )

    result = runner.invoke(app, ["recommend"])
    rows = [line for line in result.stderr.splitlines() if "A-Model-" in line]

    # Twelve models, each fitting at all three widths.
    assert len(rows) == 36


def test_recommend_prints_a_licence_it_cannot_read(here, monkeypatch):
    # Null on one open-weight row, a date on another. Nothing branches on it.
    dated = _listed("A-Dated-Licence-7B", "7B")
    dated["operational"]["license"] = "Open weights 2026-07-27"
    absent = _listed("A-Licenceless-7B", "7B")
    absent["operational"]["license"] = None
    _leaderboard(monkeypatch, models=[dated, absent])

    result = runner.invoke(app, ["recommend"])

    assert "Open weights 2026-07-27" in result.stderr
    assert "A-Licenceless-7B" in result.stderr


def test_recommend_says_a_machine_nothing_fits_is_not_the_problem(here, monkeypatch):
    _leaderboard(monkeypatch, models=[_listed("A-Model-400B", "400B")])

    result = runner.invoke(app, ["recommend"])

    assert result.exit_code == 0
    assert "Nothing on this list fits" in result.stderr
    assert "offgrid setup" in result.stderr


def _ranked(stderr: str) -> list[tuple[str, str]]:
    """Read back what was printed, as the order of model and width."""
    rows = [line.split() for line in stderr.splitlines() if "-bit" in line]

    return [
        (row[0], next(word for word in row if word.endswith("-bit"))) for row in rows
    ]


def test_recommend_ranks_the_best_first_and_not_the_order_it_read_them(
    here, monkeypatch
):
    # The dense model scores four points higher on the benchmark and decodes
    # at a third the speed, and is listed first in what is parsed.
    _leaderboard(
        monkeypatch,
        models=[
            _listed("A-Dense-27B", "27B", score=77.2),
            _listed("A-Mixture-35B", "35B", score=73.4, active="3B"),
        ],
    )

    result = runner.invoke(app, ["recommend"])

    assert _ranked(result.stderr) == [
        ("A-Mixture-35B", "4-bit"),
        ("A-Dense-27B", "4-bit"),
        ("A-Mixture-35B", "8-bit"),
        ("A-Dense-27B", "8-bit"),
    ]


def test_recommend_reaches_the_shortlist_docs_models_arrived_at_by_hand(
    here, monkeypatch
):
    # The whole path against the captured table. `docs/models.md` concluded
    # by hand that the mixture at 4-bit is the model for this machine, above
    # a dense model with a higher published score. Nothing here read it.
    fixture = pathlib.Path(__file__).parent / "fixtures" / "onyx_leaderboard.txt"
    monkeypatch.setattr("offgrid.cli.fetch", fixture.read_text)

    result = runner.invoke(app, ["recommend"])

    assert _ranked(result.stderr) == [
        ("Qwen3.6-35B-A3B", "4-bit"),
        ("Qwen3.6-27B", "4-bit"),
        ("Qwen3.6-35B-A3B", "8-bit"),
        ("Qwen3.6-27B", "8-bit"),
    ]


def test_recommend_states_the_quality_the_score_and_the_speed_of_each_row(
    here, monkeypatch
):
    _leaderboard(
        monkeypatch, models=[_listed("A-Mixture-35B", "35B", score=73.4, active="3B")]
    )

    result = runner.invoke(app, ["recommend"])
    row = next(line for line in result.stderr.splitlines() if "A-Mixture-35B" in line)

    assert "excellent 88" in row
    assert "73.4" in row
    assert "56" in row


def test_recommend_leaves_out_a_model_the_table_scores_at_nothing(here, monkeypatch):
    # Unmeasured is not bad. Ranking it last would say it was.
    _leaderboard(
        monkeypatch,
        models=[
            _listed("A-Unscored-7B", "7B", score=None),
            _listed("A-Scored-7B", "7B"),
        ],
    )

    result = runner.invoke(app, ["recommend"])

    assert "A-Unscored-7B" not in result.stderr
    assert "A-Scored-7B" in result.stderr


def test_recommend_leaves_the_speed_blank_on_a_chip_nobody_measured(here, monkeypatch):
    # The row still ranks on its published figures; only the estimate is
    # missing, and it is visibly missing rather than quietly wrong.
    monkeypatch.setattr(
        "offgrid.cli.detect",
        lambda: Machine(
            chip="Apple M9 Extreme",
            memory_bytes=64 * GIB,
            wired_limit_bytes=56 * GIB,
        ),
    )
    _leaderboard(monkeypatch, models=[_listed("A-Model-35B", "35B", active="3B")])

    result = runner.invoke(app, ["recommend"])
    row = next(line for line in result.stderr.splitlines() if "A-Model-35B" in line)

    assert result.exit_code == 0
    assert "56" not in row
    assert "—" in row


def test_recommend_says_what_stopped_it_rather_than_raising(here, monkeypatch):
    from offgrid.exceptions import LeaderboardUnavailableError

    def unreachable():
        raise LeaderboardUnavailableError("could not reach the leaderboard")

    monkeypatch.setattr("offgrid.cli.fetch", unreachable)

    result = runner.invoke(app, ["recommend"])

    assert result.exit_code == 1
    assert "could not reach the leaderboard" in result.stderr


def test_recommend_says_everything_it_says_to_stderr(here, monkeypatch):
    # stdout belongs to whatever is being piped somewhere, as it does in the
    # other commands.
    _leaderboard(monkeypatch, models=[_listed("A-Model-35B", "35B")])

    result = runner.invoke(app, ["recommend"])

    assert result.stdout == ""
    assert "A-Model-35B" in result.stderr


def test_recommend_writes_nothing(here, monkeypatch):
    # A model worth recommending is one that is not downloaded, and a profile
    # naming it would make the next `run` ask the runtime for what is absent.
    runner.invoke(app, ["setup"])
    before = (here / "profile.yaml").read_text()
    _leaderboard(monkeypatch, models=[_listed("A-Model-35B", "35B")])

    runner.invoke(app, ["recommend"])

    assert (here / "profile.yaml").read_text() == before
