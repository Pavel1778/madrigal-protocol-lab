"""Hypothesis engine: classification, corpus verification, versioning.

Submodules are imported from their own paths (``src.hypothesis.corpus``,
``src.hypothesis.versioning``) to keep the protocol package free of a circular
import at load time.
"""

from .status import ALL_STATUSES, CORE_STATUSES, Status

__all__ = [
    "ALL_STATUSES",
    "CORE_STATUSES",
    "Status",
]

