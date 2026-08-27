"""Hold a model, start the agent against it, and let it go afterwards."""

import typer

from offgrid.cli.binding import bind_run
from offgrid.cli.reporting import reporting
from offgrid.domain.profile import DEFAULT_PATH
from offgrid.domain.running import discarded_windows
from offgrid.domain.running.answering import hold_model
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
    read_what_was_typed,
    settle_what_to_run,
)
from offgrid.shared.say import tell
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
) -> None:
    """Start the agent against a model the runtime is holding."""
    passthrough = tuple(context.args)

    # Said in blocks rather than behind `@reporting()`, which is how the other
    # commands read what they read: the second one below wraps a single
    # statement inside the `try` that owes the release, and a decorator can
    # only mean a whole function. One command spelling it both ways is worse
    # than one command spelling it differently.
    with reporting():
        profile, runtime, agent = bind_run(DEFAULT_PATH, passthrough)
        model_request = settle_what_to_run(
            read_what_was_typed(identifier=model_name, context_window=context_window),
            stored=profile.model,
        )

        # A dialect that cannot be paired, a run that could send something off
        # this machine and a window the run could not work at are all settled
        # before the load — the first two here, the window inside `hold_model`
        # — because a load is tens of seconds nobody gets back.
        terms = agent.terms

        require_compatible(runtime.dialects, terms.dialect)
        agent.configure()
        require_nothing_leaves(agent.read_what_leaves_this_machine())

        what_the_runtime_discarded = discarded_windows.read_discarded_windows(
            profile.runtime.name,
            profile.runtime.host,
            discarded_windows.DEFAULT_PATH,
        )
        model = hold_model(
            runtime,
            model_request,
            context_floor=terms.context_floor,
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
            refuse_a_served_window_below_the_floor(model, floor=terms.context_floor)

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
                runtime=profile.runtime.name,
                host=profile.runtime.host,
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

    raise typer.Exit(code)
