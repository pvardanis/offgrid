"""Adapters for the servers that hold models in memory.

The registry is the whole public face of this package, and the one place a
name becomes an adapter. Nothing else is exported beside it: `import-linter`
reads import statements as written, so a re-exported `LMStudio` would be
indistinguishable from the `RUNTIMES` import the command line legitimately
makes — and the rule that only a registry may import a concrete adapter would
stop being checkable.
"""

from offgrid.runtime import Connect, RuntimeName
from offgrid.runtimes import lmstudio

RUNTIMES: dict[RuntimeName, Connect] = {RuntimeName.LMSTUDIO: lmstudio.connect}
