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
from offgrid.domain.running.hosted_tools import require_hosted_tools_denied
from offgrid.domain.running.launch import explain_why_it_would_not_start, start
from offgrid.domain.running.model import (
    Model,
    ModelRequest,
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

        # A dialect that cannot be paired, a run that would undo a guarantee
        # and a window the run could not work at are all settled before the
        # load — the first two here, the window inside `hold_model` — because
        # a load is tens of seconds nobody gets back.
        require_compatible(runtime.dialect, agent.dialect)
        agent.configure()
        require_hosted_tools_denied(agent.read_hosted_tools())

        model = hold_model(
            runtime,
            model_request,
            context_floor=agent.context_floor,
            runtime_host=profile.runtime.host,
        )

    # Nothing between here and the agent finishing may leave the model held:
    # from this line on, letting go is owed whatever happens.
    try:
        # What the runtime settled on rather than what was asked of it, which
        # is the only window the agent will actually start in. The load is
        # spent either way; what this saves is the agent failing on its own
        # terms, about an initial prompt rather than about the window.
        with reporting():
            refuse_a_served_window_below_the_floor(model, floor=agent.context_floor)

        served = describe_what_was_stated(model.context_window)

        tell(f"{model.identifier}, window {served}")

        discarded = _notice_a_discarded_window(
            model_request, model, host=profile.runtime.host
        )
        if discarded is not None:
            tell(discarded)

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


def _notice_a_discarded_window(
    model_request: ModelRequest, model: Model, *, host: str
) -> str | None:
    """Record and describe a window the runtime is not serving the run at.

    Two sentences, because two different things are known: offgrid asked and
    was refused, or it asked for nothing this run because a discard was
    already remembered, and says what is there instead.

    :param model_request: What the run asked for, before anything was held.
    :param model: The model as the runtime now serves it.
    :param host: Address the runtime listens on.

    :return: What to tell whoever ran offgrid, or ``None`` where the window
        asked for is the one being served, or where none was asked for.
    """
    asked_for, served = model_request.context_window, model.context_window

    if asked_for is None or served is None or served == asked_for:
        return None

    kept = discarded_windows.DEFAULT_PATH
    remembered = discarded_windows.read_discarded_window(host, model.identifier, kept)

    if remembered is not None:
        return (
            f"{model.identifier} is already held at {served}, and {asked_for} "
            f"was asked for. The runtime discarded that window on "
            f"{remembered.noticed_at.split('T')[0]}, so offgrid is using what "
            "is there."
        )

    discarded_windows.save_discarded_window(
        host=host,
        identifier=model.identifier,
        asked_for=asked_for,
        served=served,
        file_path=kept,
    )

    return (
        f"offgrid asked the runtime to hold {model.identifier} at {asked_for} "
        f"and it is serving {served}. Later runs will use what it serves "
        f"rather than asking again; delete {kept} to ask again."
    )
