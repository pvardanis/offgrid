"""The four things offgrid does: describe, check, recommend, and launch."""

import errno
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import typer

from offgrid.agents.claude_code import dialect as agent_dialect
from offgrid.agents.claude_code import plan, prepare
from offgrid.dialect import require_compatible
from offgrid.exceptions import OffgridError, ProfileError
from offgrid.fit import sizes_that_fit
from offgrid.hold import held, hold, let_go
from offgrid.launch import start
from offgrid.leaderboards.onyx import URL as LEADERBOARD
from offgrid.leaderboards.onyx import fetch, parse
from offgrid.listing import Fit, widths_that_fit
from offgrid.machine import BYTES_PER_MB, Machine, detect
from offgrid.profile import DEFAULT_PATH, Profile, save
from offgrid.profile import load as load_profile
from offgrid.quality import Quality, quality
from offgrid.runtimes.lmstudio import dialect as runtime_dialect
from offgrid.speed import tokens_per_second

CONFIG_DIR = Path.home() / ".offgrid" / "claude-code"
DEFAULT_HOST = "127.0.0.1:1234"
# The local server ignores it; the agent refuses to start without one.
TOKEN = "local"
BILLION = 1e9
GIB = 1024**3

# What to suggest the GPU be allowed of the machine's memory, leaving the rest
# for everything that is not the model.
WIRED_SHARE = 0.875

# One layout, so the heading and the models under it cannot drift apart.
COLUMNS = (
    "    {model:<22}{quality:>14}{score:>7}{speed:>7}"
    "{weights:>9}  {quant:<7}{context:>8}  {license}"
)
HEADING = COLUMNS.format(
    model="model",
    quality="quality",
    score="swe",
    speed="tok/s",
    weights="weights",
    quant="quant",
    context="context",
    license="license",
)

# What a column says where offgrid has no figure for it, as against a figure
# it has and prints.
NOTHING = "—"

app = typer.Typer(add_completion=False)


@app.callback()
def offgrid() -> None:
    """Run a coding agent against a model on this machine."""
    # This docstring is the help a person reads, so the rest is said here:
    # the callback runs before every command, and is where the command line
    # attaches its own logging. The modules below it attach none.
    _say_on_stderr()


@app.command()
def setup(
    host: str = typer.Option(None, help="Where the runtime listens."),
) -> None:
    """Measure this machine and record how to reach the runtime."""
    machine = detect()
    stored = _stored()
    profile = (
        stored.remeasured(machine, host=host)
        if stored
        else Profile.describing(machine, host=host or DEFAULT_HOST)
    )
    save(profile, DEFAULT_PATH)

    _tell(f"  {machine.chip} · {machine.memory_bytes / GIB:.0f}GB unified memory")
    limit = machine.wired_limit_bytes
    _tell(
        f"  GPU limit  {limit / GIB:.0f}GB" if limit else "  GPU limit  at its default"
    )
    _tell(f"  usable     {machine.usable_bytes / 1e9:.0f}GB")
    _tell("")
    _tell("  A model of about this size fits, leaving room for context:")
    _tell("")
    for bits, parameters in sizes_that_fit(machine):
        _tell(f"    {bits:>2}-bit   {parameters / BILLION:>5.0f}B parameters")
    _tell("")
    _tell(f"  Load one in your runtime, then `offgrid run`. Profile: {DEFAULT_PATH}")

    _tell_block(_raising_the_gpu_limit(machine))


@app.command()
def doctor() -> None:
    """Check that the runtime is reachable and holding a model."""
    profile = _profile()

    with _reported():
        model = held(profile)

    _tell(f"  runtime   {profile.host} reachable")
    _tell(f"  model     {model.identifier}")
    _tell(f"  context   {model.context_limit or 'unstated'}")
    _tell(f"  agent     {profile.agent}, speaking {agent_dialect().value}")


@app.command()
def recommend() -> None:
    """List the models a published table names that this machine can hold."""
    machine = detect()

    with _reported():
        table = parse(fetch())

    fits = _ranked(
        [
            fit
            for listing in table.listings
            if listing.coding_score is not None
            for fit in widths_that_fit(listing, machine)
        ],
        machine,
    )

    _tell("  Models that fit this machine, from the list at")
    _tell(f"  {LEADERBOARD}, table dated {table.dated or 'undated'}.")
    _tell("")

    if not fits:
        _tell("  Nothing on this list fits this machine. That is this list rather")
        _tell("  than this machine: `offgrid setup` says how much room there is,")
        _tell("  and how to raise it.")
        return

    _tell(HEADING)
    for judged, fit in fits:
        _tell(_row(fit, judged, machine))

    _tell("")
    _tell("  Download one in your runtime, then `offgrid run`.")


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def run(
    context: typer.Context,
    model_name: str = typer.Option(
        None,
        "--model",
        "-m",
        help="Load and use this model instead of the resident one.",
    ),
) -> None:
    """Start the agent against a model the runtime is holding."""
    profile = _profile()
    wanted = model_name or profile.model

    with _reported():
        # A dialect that cannot be paired and settings that would undo a
        # guarantee are both knowable before a load, and a load is tens of
        # seconds nobody gets back.
        require_compatible(runtime_dialect(), agent_dialect())
        prepare(CONFIG_DIR)

        model = hold(profile, wanted) if wanted else held(profile)

    # Nothing between here and the agent finishing may leave the model held:
    # from this line on, letting go is owed whatever happens.
    try:
        _tell(f"  {model.identifier}, context {model.context_limit or 'unstated'}")

        launch = plan(
            model,
            host=profile.host,
            config_dir=CONFIG_DIR,
            token=TOKEN,
            passthrough=list(context.args),
        )

        try:
            code = start(launch)
        except OSError as error:
            _tell(_would_not_start(launch.argv[0], error))
            code = 127
    except KeyboardInterrupt:
        code = 130
    finally:
        let_go(profile.host, model.identifier)

    raise typer.Exit(code)


class _Stderr(logging.StreamHandler):
    """A handler that writes to stderr as it is now.

    A handler that captured the stream it was built on writes into a closed
    buffer once whoever owned that stream is finished with it, and logging
    reports that as a traceback over whatever is being read at the time.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """Write a record to the stream stderr names at this moment.

        :param record: What to write.
        """
        self.stream = sys.stderr
        super().emit(record)


def _say_on_stderr() -> None:
    """Print what offgrid says, as the words and nothing else.

    A library configures no logging; the command line does. It goes to
    stderr so that stdout carries whatever the agent has to say. Only the
    handler this installs is replaced, because a caller that put its own
    there meant it.
    """
    logger = logging.getLogger("offgrid")

    for existing in [h for h in logger.handlers if isinstance(h, _Stderr)]:
        logger.removeHandler(existing)

    handler = _Stderr()
    handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _would_not_start(command: str, error: OSError) -> str:
    """Say what stopped the agent starting, and what to do about that.

    A missing command and a command without the bit that makes it runnable
    fail the same way and are fixed differently, so the advice follows the
    reason rather than the operation.

    :param command: What was being started.
    :param error: Why it was not.

    :return: What to say.
    """
    advice = {
        errno.ENOENT: "Install it, or put it on PATH.",
        errno.EACCES: "It is there but not executable.",
    }.get(error.errno, "")

    return f"  Could not start {command}: {error}. {advice}".rstrip()


def _raising_the_gpu_limit(machine: Machine) -> list[str]:
    """Say how to give the GPU more of the memory, where it has not been given.

    This is the one thing offgrid can suggest that changes what fits.

    :param machine: The host, as it is set up now.

    :return: The lines to say, or none where the limit is already raised.
    """
    if machine.wired_limit_bytes is not None:
        return []

    wanted = int(machine.memory_bytes * WIRED_SHARE / BYTES_PER_MB)

    return [
        "  More fits with the GPU limit raised, which a reboot undoes:",
        f"    sudo sysctl iogpu.wired_limit_mb={wanted}",
    ]


def _tell_block(lines: list[str]) -> None:
    """Say a group of lines under a blank one, or nothing where there are none.

    :param lines: What to say.
    """
    if not lines:
        return

    _tell("")
    for line in lines:
        _tell(line)


def _ranked(fits: list[Fit], machine: Machine) -> list[tuple[Quality, Fit]]:
    """Put the best of what fits first, judging each one once.

    :param fits: Every model at every width this machine holds it at.
    :param machine: The host they would run on.

    :return: Each fit with what it was judged to be worth, best first, and
        the leaner width first where two are judged the same — the cheaper
        build is the one to read as the default.
    """
    judged = [(quality(fit, machine), fit) for fit in fits]

    return sorted(judged, key=lambda pair: (-pair[0].score, pair[1].quantization_bits))


def _row(fit: Fit, judged: Quality, machine: Machine) -> str:
    """Lay out one model of the recommendation.

    :param fit: The model, at one of the widths this machine holds it at.
    :param judged: What that fit is worth here.
    :param machine: The host it would run on.

    :return: The line to say.
    """
    # Every row reaching here has a score: a listing without one is dropped
    # before anything is ranked, since it cannot be.
    published = fit.listing.coding_score
    speed = tokens_per_second(fit, machine)

    return COLUMNS.format(
        model=fit.listing.name,
        quality=f"{judged.label} {judged.score}",
        score=f"{published:.1f}",
        speed=f"~{speed:.0f}" if speed else NOTHING,
        weights=f"{fit.weights_bytes / 1e9:.1f}GB",
        quant=f"{fit.quantization_bits}-bit",
        context=str(fit.listing.context_window or "unstated"),
        # Printed, never read: it is absent on one open-weight row and a
        # date on another, so nothing here can branch on it.
        license=fit.listing.license or "unstated",
    )


def _tell(message: str) -> None:
    """Say something to whoever is running offgrid.

    :param message: What to say.
    """
    typer.echo(message, err=True)


@contextmanager
def _reported() -> Iterator[None]:
    """Say what went wrong and stop, rather than raising at the terminal.

    offgrid's own errors carry the operation, the input and what to do next,
    which a traceback buries.

    :yield: To the operation being run.
    """
    try:
        yield
    except OffgridError as error:
        _tell(f"  {error}")
        raise typer.Exit(1) from error


def _stored() -> Profile | None:
    """Read the profile already there, so a re-run does not undo an edit.

    :return: The stored profile, or ``None`` when there is none to keep.
    """
    if not DEFAULT_PATH.exists():
        return None

    try:
        return load_profile(DEFAULT_PATH)
    except ProfileError as error:
        kept = DEFAULT_PATH.with_suffix(".yaml.rejected")
        kept.write_text(DEFAULT_PATH.read_text())

        _tell(f"  {error}")
        _tell(f"  What was there is at {kept}. Writing a fresh profile.")
        return None


def _profile() -> Profile:
    """Read the stored profile, or explain how to make one.

    :return: The stored profile.
    """
    with _reported():
        return load_profile(DEFAULT_PATH)


def main() -> None:
    """Run the command line, reporting offgrid's own errors as messages.

    A command reports what it can itself. This is the net under everything
    else, so an error offgrid raised on purpose reaches the terminal as the
    sentence it was written as rather than as a traceback.
    """
    try:
        app()
    except OffgridError as error:
        _tell(f"  {error}")
        sys.exit(1)
