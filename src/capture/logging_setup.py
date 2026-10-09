"""Logging configuration shared by the command line entry points.

By default the libraries stay quiet and only the CLI prints its summary. Passing
``--verbose`` turns on the informational and debug lines emitted by the capture,
project and report modules, which is how a run on a large capture can be
followed.
"""

from __future__ import annotations

import logging

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(verbose: bool) -> None:
    """Install a stderr handler; level is INFO when ``verbose``, else WARNING."""

    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(level=level, format=_FORMAT)
    # basicConfig is a no-op once a handler exists; set the root level too so a
    # second call (for example from a test) still takes effect.
    logging.getLogger().setLevel(level)
