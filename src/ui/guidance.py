"""Plain-language guidance shown next to the technical panels.

The laboratory is used by people who did not read a manual: an engineer who
recorded some traffic and wants to know what the bytes mean. The panels
themselves speak in protocol terms (framing, hypothesis, counterexample), so
every panel carries a one-line explanation of what it is for and what to do
with it. Keeping those sentences in one module means the same wording is used
in the window, in the help card and in the tests, and a translator edits them
in a single place.

Each helper returns a short sentence. They are wrapped in :meth:`QObject.tr`
through the window, so the Russian catalogue supplies the translation.
"""

from __future__ import annotations

# What each status means, in words a non-specialist can act on. The keys are
# the engine's status values; the value is a full sentence for a tooltip.
STATUS_MEANING: dict[str, str] = {
    "matched": "The rule describes these bytes and the bytes agree with it.",
    "mismatched": "A counterexample: the bytes break the rule, so the rule is wrong here.",
    "incomplete": "The message runs past a hole in the capture, so it cannot be read in full.",
    "ambiguous": "Two copies of the same bytes disagree, so the value cannot be trusted.",
    "uncovered": "No field of the rule claims these bytes yet.",
    "not_applicable": "The rule does not apply to this direction.",
    "outdated": "This verdict came from an older version of the rule.",
    "unknown": "The bytes could not be classified.",
}

# One sentence per panel: what it holds and what the reader should do with it.
SESSIONS_PANEL = (
    "Every TCP conversation found in the capture. Pick one to see its bytes."
)
BYTES_PANEL = (
    "The reassembled bytes of the chosen direction. Hover a byte to see where it "
    "came from; the colours show how the current rule reads them."
)
INTERPRETATION_PANEL = (
    "The rule that says how to read the messages, and what it found. A rule is a "
    "guess about the format; the messages below show whether the guess held."
)
COUNTEREXAMPLES_PANEL = (
    "Messages that break the rule. Each one is evidence the rule is wrong, kept "
    "against it rather than hidden. Click a row to jump to its bytes."
)
HYPOTHESES_PANEL = (
    "Fields the rule marks as a guess. The alternatives are other readings of the "
    "same bytes; a high score is evidence, not proof."
)
COMPARE_PANEL = (
    "Two messages side by side, with the bytes that differ highlighted."
)
REPORT_PANEL = (
    "The written report of the investigation: what was found, what was assumed, "
    "and every counterexample."
)
VERSION_DIFF_PANEL = (
    "What changed between two versions of the rule, and how the verdicts moved."
)

# The three-step workflow, used by the welcome panel and the help card.
STEPS: tuple[tuple[str, str], ...] = (
    (
        "1. Open a capture",
        (
            "Load a recorded file (PCAP, PCAPNG or a normalized JSON). "
            "Not sure where to start? Open the built-in demo."
        ),
    ),
    (
        "2. Pick a conversation",
        "Choose one session on the left, then a direction. The bytes appear in the middle.",
    ),
    (
        "3. Describe the messages",
        (
            "Load a rule, or build one from the bytes you select. The tool then checks "
            "the rule against every message and shows what disagrees."
        ),
    ),
)


def status_meaning(status: str) -> str:
    """Return the plain-language meaning of a status, or an empty string."""
    return STATUS_MEANING.get(status, "")
