"""Investigation reports in Markdown and HTML.

Public API:

- :func:`render_markdown` - write an investigation as Markdown
- :func:`render_html` - write an investigation as a self-contained HTML page
- :func:`normalize` - fill an investigation dictionary to the report shape
"""

from __future__ import annotations

from src.report.html import render_html
from src.report.markdown import render_markdown
from src.report.model import ReportError, normalize, status_label

__all__ = [
    "ReportError",
    "normalize",
    "render_html",
    "render_markdown",
    "status_label",
]
