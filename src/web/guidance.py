"""Plain-language guidance for the web interface.

The desktop window and the web page explain the same three-step workflow in the
same words, so a reader who learns one recognises the other. The strings live
here rather than in the templates so they can be tested without rendering a
page.
"""

from __future__ import annotations

# The three steps, in the order a first-time reader meets them.
STEPS: tuple[tuple[str, str], ...] = (
    (
        "1. Open a capture",
        "Load a recorded file (PCAP, PCAPNG or a normalized JSON). "
        "Not sure where to start? Open the built-in demo.",
    ),
    (
        "2. Pick a conversation",
        "Choose one session and a direction. The bytes appear as hex.",
    ),
    (
        "3. Read the messages",
        "Load a rule, or let the bundled one describe the demo. "
        "The tool checks the rule against every message and marks what disagrees.",
    ),
)

# What each verdict means, in one sentence. Shown as the legend and as the
# per-message tooltip.
STATUS_MEANINGS: dict[str, str] = {
    "matched": "the bytes agree with the rule",
    "mismatched": "a counterexample: the bytes break the rule here",
    "incomplete": "the message is cut by a gap in the capture",
    "ambiguous": "two readings fit the same bytes",
    "uncovered": "no field of the rule claims these bytes yet",
    "not_applicable": "the rule does not apply to this direction",
    "outdated": "produced by an earlier version of the rule",
    "unknown": "not classified",
}


def status_meaning(status: str) -> str:
    """One sentence describing *status*, or a neutral fallback."""
    return STATUS_MEANINGS.get(status, "not classified")
