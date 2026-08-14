"""Where offgrid keeps what it remembers between runs.

Its own module because `agent.py` needs it to derive the directory an agent is
run out of, and `profile.py` needs it for the file — and `profile.py` already
imports `agent.py`, so the constant cannot live there without a cycle.
"""

from pathlib import Path

OFFGRID_HOME = Path.home() / ".offgrid"
