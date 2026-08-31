"""Hold a model, start the agent against it, and let it go afterwards."""

import typer

from offgrid.cli.binding import bind_profile, bind_run, read_what_could_be_run
from offgrid.cli.reporting import reporting
from offgrid.domain.assembling import describe_what_a_save_wrote
from offgrid.domain.profile import DEFAULT_PATH, Profile, save_profile
from offgrid.domain.running import discarded_windows
from offgrid.domain.running.agent import Agent, Passthrough
from offgrid.domain.running.answering import find_resident_model, hold_model
from offgrid.domain.running.context_window import (
    refuse_a_served_window_below_the_floor,
)
from offgrid.domain.running.dialect import require_compatible
from offgrid.domain.running.discarding import (
    read_what_became_of_the_window,
    refuse_to_ask_runtime_again,
    save_discarded_window_if_new,
)
from offgrid.domain.running.launch import explain_why_it_would_not_start, start
from offgrid.domain.running.leaving import require_nothing_leaves
from offgrid.domain.running.model import (
    ModelRequest,
    read_what_was_typed,
    settle_what_to_run,
)
from offgrid.domain.running.runtime import Runtime
from offgrid.shared.say import every_stream_is_a_terminal, tell
from offgrid.shared.wording import describe_what_was_stated


def run(
    context: typer.Context,
    model_name: str = typer.Option(
        None,
        "--model",
        "-m",
        help="Load and use this model instead of the resident one.",
    ),
    context_window: int = typer.Option(
        None,
        "--context-window",
        min=1,
        help="Hold the model at this window. Left out, the runtime's own is used.",
    ),
    no_input: bool = typer.Option(
        False,
        "--no-input",
        help="Refuse a dead end rather than opening the picker, even at a terminal.",
    ),
) -> None:
    """Start the agent against a model, or open the picker at a dead end.

    A dead end a person could answer — a terminal, nothing named, and the
    runtime holding nothing — opens the picker rather than refusing, so the
    choice a refusal only named can be made on the spot. Every other path is
    the run it has always been.
    """
    passthrough = tuple(context.args)

    with reporting():
        profile, runtime, agent = bind_run(DEFAULT_PATH, passthrough)
        model_request = settle_what_to_run(
            read_what_was_typed(identifier=model_name, context_window=context_window),
            stored=profile.model,
        )
        opens_the_picker = _a_dead_end_a_person_could_answer(
            model_request, passthrough, runtime, no_input=no_input
        )

    # Opened outside the reporting block, as bare `offgrid` opens it: a screen
    # takes the terminal, and the logging that turns an error into a line is
    # for the plain-text run on either side of it, not for the screen between.
    if opens_the_picker:
        open_the_picker()

        return

    raise typer.Exit(launch_a_run(profile, runtime, agent, model_request))


def _a_dead_end_a_person_could_answer(
    model_request: ModelRequest,
    passthrough: Passthrough,
    runtime: Runtime,
    *,
    no_input: bool,
) -> bool:
    """Whether this run is the dead end the picker opens over, not refuses.

    Four conditions, all of them: a person at the terminal to answer, nothing
    named on the command line, nothing named in the profile, and the runtime
    holding nothing. Any one missing is today's refusal, which `launch_a_run`
    still makes. `--no-input` forces that refusal even where a person is there.

    The runtime is asked last and only where the rest hold, so a run that has
    something to do never pays for the extra reading. A resident run at a
    terminal reads the runtime once here and again in `hold_model`; every other
    run reads it at most once.

    :param model_request: What the command line and profile settled on.
    :param passthrough: What was handed through to the agent.
    :param runtime: The runtime a run would talk to.
    :param no_input: Whether the run was told to refuse rather than ask.

    :return: Whether to open the picker instead of running.
    """
    if no_input or passthrough:
        return False

    if model_request.identifier is not None or model_request.context_window is not None:
        return False

    if not every_stream_is_a_terminal():
        return False

    return find_resident_model(runtime) is None


def open_the_picker() -> None:
    """Open the screen offgrid opens with nothing to do, and run what it hands back.

    The same screen bare `offgrid` opens, reached instead from a `run` that
    found a dead end a person could answer. It is handed its reading and how it
    saves, so it names no registry; what a key ends it with is carried out here
    in the plain lines a run is read in, after the screen is gone.

    :raise Exit: With the screen's own code where it died, or with the code the
        run it handed back finished on. A screen left with `q` raises nothing
        and the command exits zero.
    """
    # Imported here rather than at the top: Textual costs an order of magnitude
    # more to import than the command line's own toolkit, and a run that never
    # reaches the picker would pay it.
    from offgrid.tui.picker import Picker

    screen = Picker(
        read_report_func=lambda: read_what_could_be_run(DEFAULT_PATH),
        save_func=lambda profile: save_profile(profile, DEFAULT_PATH),
    )
    departure = screen.run()

    # Textual paints what went wrong on the screen and returns rather than
    # raising it, so the code it set is the only thing that says the screen
    # died. Unread, a crash under a traceback exits like a report somebody read.
    if screen.return_code:
        raise typer.Exit(screen.return_code)

    if departure is not None:
        launch_the_assembled_profile(departure.profile, saved=departure.saved)


def launch_the_assembled_profile(profile: Profile, *, saved: bool) -> None:
    """Run what the picker handed back, in the plain lines a run is read in.

    The screen has settled runtime, agent and model into a profile and, where
    the key that writes was pressed, already saved it. What is left is the run
    itself, said the same way whether it was reached from here or a command
    line, and the sentence that says what a save wrote — printed here rather
    than on the screen, which is gone by the time this runs.

    :param profile: What the picker assembled.
    :param saved: Whether the profile was saved, which is what the report of it
        is about.

    :raise Exit: With the code the run finished on, as `run` raises it.
    """
    if saved:
        tell(describe_what_a_save_wrote(profile))

    with reporting():
        profile, runtime, agent = bind_profile(profile)
        model_request = settle_what_to_run(
            read_what_was_typed(identifier=None, context_window=None),
            stored=profile.model,
        )

    raise typer.Exit(launch_a_run(profile, runtime, agent, model_request))


def launch_a_run(
    profile: Profile, runtime: Runtime, agent: Agent, model_request: ModelRequest
) -> int:
    """Hold the model, start the agent against it, and let it go afterwards.

    The run sequence, from the checks that cost nothing through to the release
    that is owed once a load has been paid for. It is one function so that a run
    reached from the picker and a run reached from a command line are the same
    eight steps, worded the same way and exiting the same way.

    :param profile: What the run is made from.
    :param runtime: The runtime holding the model.
    :param agent: The agent to start.
    :param model_request: The model to hold, and the window to hold it at.

    :return: The code the run finished on.
    """
    # Said in blocks rather than behind `@reporting()`, which is how the other
    # commands read what they read: the second one below wraps a single
    # statement inside the `try` that owes the release, and a decorator can
    # only mean a whole function. One command spelling it both ways is worse
    # than one command spelling it differently.
    with reporting():
        # A dialect that cannot be paired, a run that could send something off
        # this machine and a window the run could not work at are all settled
        # before the load — the first two here, the window inside `hold_model`
        # — because a load is tens of seconds nobody gets back.
        agent_terms = agent.terms

        require_compatible(runtime.dialects, agent_terms.dialect)
        agent.configure()
        require_nothing_leaves(agent.read_what_leaves_this_machine())

        what_the_runtime_discarded = discarded_windows.read_discarded_windows(
            profile.runtime_name,
            profile.runtime_host,
            discarded_windows.DEFAULT_PATH,
        )
        model = hold_model(
            runtime,
            model_request,
            context_floor=agent_terms.context_floor,
            was_window_refused_func=refuse_to_ask_runtime_again(
                what_the_runtime_discarded
            ),
        )

    # Nothing between here and the agent finishing may leave the model held:
    # from this line on, letting go is owed whatever happens.
    try:
        # What the runtime settled on rather than what was asked of it, which
        # is the only window the agent will actually start in. The load is
        # spent either way; what this saves is the agent failing on its own
        # terms, about an initial prompt rather than about the window.
        with reporting():
            refuse_a_served_window_below_the_floor(
                model, floor=agent_terms.context_floor
            )

        served = describe_what_was_stated(model.context_window)

        tell(f"{model.identifier}, window {served}")

        what_became_of_the_window = read_what_became_of_the_window(
            what_the_runtime_discarded, model_request, model
        )
        if what_became_of_the_window is not None:
            tell(what_became_of_the_window.said)
            complaint = save_discarded_window_if_new(
                what_became_of_the_window,
                model,
                runtime=profile.runtime_name,
                host=profile.runtime_host,
                file_path=discarded_windows.DEFAULT_PATH,
            )
            if complaint is not None:
                tell(complaint)

        launch = agent.plan(model)
        # Said whenever there is anything at all, so an agent answering with
        # an empty one shows as a blank line somebody reports rather than as
        # a warning nobody was given.
        if launch.caution is not None:
            tell(f"{launch.caution}")

        try:
            code = start(launch)
        except OSError as error:
            tell(explain_why_it_would_not_start(launch.argv[0], error))
            code = 127
    except KeyboardInterrupt:
        code = 130
    finally:
        runtime.let_go(model.identifier)

    return code
