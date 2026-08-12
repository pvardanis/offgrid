"""How Claude Code is started, and what it is given to work in."""

# Decode runs at tens of tokens per second, so thinking and long replies cost
# wall time directly.
MAX_OUTPUT_TOKENS = 8192

# Used when the runtime states no context for a model. Small enough to be
# served by anything, large enough to hold a conversation.
FALLBACK_CONTEXT = 32768


def get_claude_args(passthrough: list[str]) -> list[str]:
    """Settle the command line Claude Code is started with.

    :param passthrough: Arguments handed to the agent unchanged.

    :return: The command and its arguments.
    """
    return [
        "claude",
        # No --mcp-config alongside it, so no servers load at all.
        "--strict-mcp-config",
        # Volatile sections move into the first message, leaving the cached
        # prefix identical between turns.
        "--exclude-dynamic-system-prompt-sections",
        *passthrough,
    ]
