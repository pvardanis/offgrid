"""Adapters for the coding agents that talk to a runtime.

The registry is the whole public face of this package, and the one place a
name becomes an adapter. Nothing else is exported beside it, for the reason
`runtimes/` states: `import-linter` reads import statements as written, so a
re-exported `ClaudeCode` would be indistinguishable from the `AGENTS` import
the command line legitimately makes.
"""

from offgrid.agent import AgentName, Prepare
from offgrid.agents import claude_code

AGENTS: dict[AgentName, Prepare] = {AgentName.CLAUDE_CODE: claude_code.prepare}
