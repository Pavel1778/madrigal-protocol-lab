"""Optional local web interface for the protocol laboratory.

A small FastAPI application that exposes the same normalized-capture contract
and rule engine the desktop window uses, over ``http://127.0.0.1``. It is a
read-only inspector: open a capture, list sessions, view the hex, apply a rule
and export the report. It never re-implements the capture or protocol engine,
it wraps it.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "1.0.0"
