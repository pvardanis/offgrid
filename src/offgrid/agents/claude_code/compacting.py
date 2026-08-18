"""What Claude Code compacts against, and what is said where it will not.

Both out of the window the runtime is serving, because a number Claude Code
will raise is a number offgrid does not ask for — and a person who is not told
meets that as a truncated prefix halfway through a session.
"""

# The setting is documented as clamped to at least this and at most the
# model's own window, so anything smaller asked for is answered with this
# instead. The documented range tops out at 1,000,000, which no model served
# on this machine reaches, so only the bottom of it is guarded here.
LOWEST_HONOURED_WINDOW = 100_000

# The setting a window is asked for through, named in what a person reads
# because it is the handle they would reach for to overrule any of this.
COMPACTION_WINDOW = "CLAUDE_CODE_AUTO_COMPACT_WINDOW"


def get_compaction_window(window: int | None) -> int | None:
    """Size compaction to what the model is served at, where that is honoured.

    :param window: What the model is being served at, or ``None`` where the
        runtime states nothing.

    :return: The window to compact against, and ``None`` where asking would
        be answered with a larger number than the runtime will serve.
    """
    if window is None or window < LOWEST_HONOURED_WINDOW:
        return None

    return window


def get_compaction_setting(
    window: int | None,
) -> tuple[dict[str, str], frozenset[str]]:
    """Settle what the agent is told about compaction, and what it is not.

    Compact before the server truncates the prefix and voids its cache, and
    only at a window Claude Code honours: below that it raises what it is
    given, so it would wait until 100,000 to compact while the runtime went on
    truncating at its own window.

    Where nothing is asked for, the setting is taken back out of what the
    agent inherits rather than merely left unwritten — an exported one would
    otherwise answer in offgrid's place, and the sentence beside it says
    nothing was set.

    :param window: What the model is being served at, or ``None`` where the
        runtime states nothing.

    :return: What to add to the agent's environment, and what to drop from
        it.
    """
    compaction = get_compaction_window(window)

    if compaction is None:
        return {}, frozenset({COMPACTION_WINDOW})

    return {COMPACTION_WINDOW: str(compaction)}, frozenset()


def explain_what_will_not_compact(window: int | None) -> str | None:
    """Say that compaction is not sized to the run, and what to do instead.

    Asked of the same window the setting is, and answered as the negation of
    it: there is something to say exactly where nothing was asked for.

    What it says is what is known. Where nothing was asked for, when the agent
    compacts is Claude Code's own business and offgrid has not been told what
    it decided — so the sentence names the setting that was left alone and the
    command that compacts on demand, rather than predicting a truncation whose
    size nobody here can state.

    :param window: What the model is being served at, or ``None`` where the
        runtime states nothing.

    :return: What to tell a person before the run starts, and ``None`` where
        compaction is sized to the window and there is nothing to say.
    """
    if get_compaction_window(window) is not None:
        return None

    why = (
        f"Claude Code will not compact below {LOWEST_HONOURED_WINDOW} and the "
        f"runtime is serving {window}"
        if window is not None
        else "The runtime states no window to size it to"
    )

    return (
        f"{why}, so {COMPACTION_WINDOW} is left unset and compaction is not "
        "sized to this run. Type /compact when the conversation gets long."
    )
