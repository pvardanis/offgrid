"""What every layer may reach, because it reaches nothing of offgrid's own.

The errors offgrid raises on purpose, how it talks to whoever ran it, where it
keeps what it remembers, and reading a config as the adapter that declared it.

Each imports only the standard library or a dependency, which is the test for
belonging here rather than a description of it — anything reaching back into
offgrid would make this layer a place cycles are written.
"""
