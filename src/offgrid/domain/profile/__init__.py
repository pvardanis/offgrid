"""What offgrid remembers between runs, and what a bad one reads like.

The public face of the package: what a caller imports, gathered here so that
the file, the refusals and the shape offgrid read before this one can each be
their own module without a caller having to know which is which.
"""

from offgrid.domain.profile.profile import (
    DEFAULT_PATH,
    Profile,
    create_profile,
    load_yaml,
    save_profile,
)
from offgrid.domain.profile.refusing import refuse_profile_section
from offgrid.domain.profile.structure import refuse_a_flat_profile

__all__ = [
    "DEFAULT_PATH",
    "Profile",
    "create_profile",
    "load_yaml",
    "refuse_a_flat_profile",
    "refuse_profile_section",
    "save_profile",
]
