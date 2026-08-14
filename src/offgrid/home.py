"""Where offgrid keeps what it remembers between runs.

Its own module because two modules that may not import each other both need
it: the profile lives here, and so does the directory each agent is given.
"""

from pathlib import Path

OFFGRID_HOME = Path.home() / ".offgrid"
