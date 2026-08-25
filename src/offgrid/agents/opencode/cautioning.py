"""What a person is owed before an OpenCode run starts, and why each of it.

A run does things to itself that somebody would otherwise meet mid-session, so
what is said about them is settled here rather than beside the settings that
cause them: they are read as one thing, in one place, before anything starts.
"""

# Said as a standing fact about an offgrid run rather than conditioned on
# whether such a file is there. Deciding that would mean reimplementing
# OpenCode's own upward directory walk, its stopping condition and both file
# spellings, to word one sentence — and a walk that drifted from theirs would
# say the wrong thing confidently. For the same reason it names what a person
# is likeliest to have rather than claiming a complete list.
PROJECT_CONFIG_CAUTION = (
    "Project configuration is not read for this run: an `opencode.json`, a "
    "`.opencode` directory and instructions such as `AGENTS.md` are skipped, "
    "in the directory you started from and every directory above it up to the "
    "project root. offgrid cannot outrank the providers, agents and "
    "permissions one of those adds, so it runs with none of them. Your own "
    "configuration under your home is read as usual. Start OpenCode yourself "
    "to use what a project states."
)
