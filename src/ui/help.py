"""The single reference catalogue for the interface.

Every explanation the learning centre shows comes from here, so a definition
lives in one place rather than being copied into a tooltip, a lesson and a
dialog. The entries describe the real parameters of the rule model
(:mod:`src.protocol.rule`), the framing strategies (:mod:`src.protocol.framing`),
the result statuses (:mod:`src.hypothesis.status`) and the quality metrics
(:mod:`src.hypothesis.metrics`); where a definition is quoted, it is the one the
code actually implements, not a generic description of the term.

Strings are stored as English source literals in ``QT_TRANSLATE_NOOP`` markers
and translated at render time, so the catalogue follows the interface language
and does not freeze the language it was first built in.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6 import QtCore

HELP_CONTEXT = "Help"

# Surfaces: which reader an entry is written for. ``simple`` is the default text;
# ``advanced`` entries assume the reader knows the basics.
SIMPLE = "simple"
ADVANCED = "advanced"


@dataclass(frozen=True)
class HelpEntry:
    """One explainable element of the interface.

    Attributes:
        key: Stable identifier, also the key other entries refer to.
        section: Grouping shown in the learning centre.
        title: The name as it appears in the interface.
        summary: One plain sentence: what it is.
        purpose: What task it serves.
        values: Allowed values, range, units or format, when defined.
        default: The value used when the reader sets nothing, and why.
        example: A concrete example on the demo data.
        effect: What changes if a different value is chosen.
        depends: Other parameters or states that change its behaviour.
        mistakes: Common wrong settings and what they cause.
        related: Keys worth reading next.
        surface: ``simple`` or ``advanced``.
    """

    key: str
    section: str
    title: str
    summary: str
    purpose: str = ""
    values: str = ""
    default: str = ""
    example: str = ""
    effect: str = ""
    depends: str = ""
    mistakes: str = ""
    related: tuple[str, ...] = field(default_factory=tuple)
    surface: str = SIMPLE


def _e(key: str, section: str, title: str, summary: str, **rest: str) -> HelpEntry:
    """Build an entry with every string marked for extraction."""
    return HelpEntry(
        key=key,
        section=QtCore.QT_TRANSLATE_NOOP("Help", section),
        title=QtCore.QT_TRANSLATE_NOOP("Help", title),
        summary=QtCore.QT_TRANSLATE_NOOP("Help", summary),
        **{name: QtCore.QT_TRANSLATE_NOOP("Help", text) for name, text in rest.items()},
    )


SECTIONS: tuple[str, ...] = (
    "Getting started",
    "The window",
    "Framing a message",
    "Fields",
    "Values and byte order",
    "The rule document",
    "Checking a rule",
    "Reading the results",
    "Everyday concepts",
)

HELP_ENTRIES: tuple[HelpEntry, ...] = (
    # -- Getting started ---------------------------------------------------
    _e(
        "capture",
        QtCore.QT_TRANSLATE_NOOP("Help", "Getting started"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Capture"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "The recording of network traffic that was opened."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A capture is the only evidence the laboratory works from; every "
            "number in a result is measured over it.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP(
            "Help", "A pcap, pcapng or normalized JSON file."
        ),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help", "The built-in example opens a small capture with three sessions."
        ),
        depends=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "The analysis is limited to the capture that is open; a second "
            "capture is studied in a second run.",
        ),
        related=("session", "message", "direction"),
    ),
    _e(
        "session",
        QtCore.QT_TRANSLATE_NOOP("Help", "Getting started"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Session"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "One conversation between two endpoints in the capture."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A protocol is read one conversation at a time, because different "
            "conversations can use different message shapes.",
        ),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "The example capture holds three sessions; the first carries the "
            "set-parameter exchange.",
        ),
        depends=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Sessions are found by connection, so a port reused later starts a "
            "new session rather than joining the old one.",
        ),
        related=("direction", "message"),
    ),
    _e(
        "direction",
        QtCore.QT_TRANSLATE_NOOP("Help", "Getting started"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Direction"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Which way the data flowed inside a session: A to B or B to A."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Requests and replies are read apart, so a rule can be scoped to "
            "one side of the exchange.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP(
            "Help", "A_to_B, B_to_A, or any direction when the rule is not scoped."
        ),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A set-parameter request travels A to B; its acknowledgement "
            "travels B to A.",
        ),
        effect=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A rule scoped to one direction is only applied to messages in that "
            "direction; the other direction is reported as not applicable.",
        ),
        related=("message", "scope"),
    ),
    _e(
        "message",
        QtCore.QT_TRANSLATE_NOOP("Help", "Getting started"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Message"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "One thing said in a session, as a range of bytes."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A message is the unit a rule describes: a rule says how messages "
            "are cut out of the stream and what each byte range means.",
        ),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help", "In the example, a set-parameter request is a five-byte message."
        ),
        depends=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Message boundaries come from the framing strategy, not from the "
            "packets; one message can span several packets.",
        ),
        related=("framing", "field"),
    ),
    _e(
        "learning_mode",
        QtCore.QT_TRANSLATE_NOOP("Help", "Getting started"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Learning mode"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "The guided presentation: the tutor panel, the step strip and the help "
            "icons are shown.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A reader who has not used the tool before is shown the order of "
            "work and can ask what any element means.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "On or off, switched from View, from the tutor panel or from Settings.",
        ),
        default=QtCore.QT_TRANSLATE_NOOP(
            "Help", "On for a fresh install, so the first screen explains the tool."
        ),
        effect=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Switching to the expert mode hides the hints; no analysis changes, "
            "only what is explained on screen.",
        ),
        related=("expert_mode", "tutor"),
    ),
    _e(
        "expert_mode",
        QtCore.QT_TRANSLATE_NOOP("Help", "Getting started"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Expert mode"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "The dense presentation: hints are hidden and the technical panels are the "
            "focus.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "An experienced reader wants the tables and the JSON without the "
            "explanations in the way.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP(
            "Help", "On or off, switched from View or from the mode control."
        ),
        effect=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Nothing is removed: every tab, field and the JSON editor stay "
            "reachable. Only the teaching text is hidden.",
        ),
        related=("learning_mode",),
        surface=ADVANCED,
    ),
    # -- The window --------------------------------------------------------
    _e(
        "sessions_box",
        QtCore.QT_TRANSLATE_NOOP("Help", "The window"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Sessions panel"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "The list of sessions and their directions on the left."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It is how a conversation is chosen; the rest of the window follows "
            "the choice.",
        ),
        related=("session", "direction"),
    ),
    _e(
        "hex_view",
        QtCore.QT_TRANSLATE_NOOP("Help", "The window"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Bytes view"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "The centre column: offset, hex and ASCII for the selected message."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It is the ground truth. Every interpretation is checked against "
            "these bytes, and clicking a byte shows where it came from.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP(
            "Help", "Click to select one byte, drag to select a range."
        ),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Offset 0 holds the command byte; selecting bytes 2 and 3 selects "
            "the length field.",
        ),
        related=("offset", "status"),
    ),
    _e(
        "right_tabs",
        QtCore.QT_TRANSLATE_NOOP("Help", "The window"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Analysis tabs"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "The right column: Interpretation, Compare, Hypotheses, Report and Version "
            "diff.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "These turn bytes into a claim (Interpretation), compare messages "
            "(Compare, Hypotheses) and write the work up (Report, Version diff).",
        ),
        related=("validation_view", "compare_view", "hypotheses_view", "report_view"),
    ),
    _e(
        "validation_view",
        QtCore.QT_TRANSLATE_NOOP("Help", "The window"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Interpretation tab"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Where a rule is written, applied and checked."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It holds the rule document, the counts of the last check and the "
            "counterexamples it found.",
        ),
        related=("apply_rule", "corpus_check", "counterexample"),
    ),
    _e(
        "compare_view",
        QtCore.QT_TRANSLATE_NOOP("Help", "The window"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Compare tab"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Two or more messages shown side by side."),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "What stays the same across messages is a candidate for a constant; "
            "what changes is a candidate for a value.",
        ),
        related=("hypotheses_view",),
    ),
    _e(
        "hypotheses_view",
        QtCore.QT_TRANSLATE_NOOP("Help", "The window"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Hypotheses tab"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Candidate readings of a field marked as a guess."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "For a field flagged as a hypothesis it lists alternative meanings "
            "and how many messages support each, so the reader chooses.",
        ),
        related=("hypothesis_flag", "counter"),
    ),
    _e(
        "report_view",
        QtCore.QT_TRANSLATE_NOOP("Help", "The window"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Report tab"),
        QtCore.QT_TRANSLATE_NOOP("Help", "The investigation written up as a document."),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It gathers the hypotheses, examples, counterexamples and open "
            "questions so the work can be handed over.",
        ),
        related=("report",),
    ),
    _e(
        "diff_view",
        QtCore.QT_TRANSLATE_NOOP("Help", "The window"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Version diff tab"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "A comparison of two rule versions or two runs."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It shows whether an edit improved the fit or moved the "
            "disagreements elsewhere.",
        ),
        related=("rule_version",),
    ),
    _e(
        "status_bar",
        QtCore.QT_TRANSLATE_NOOP("Help", "The window"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Status line"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "The bottom strip: the provenance of the byte under the cursor and a "
            "progress bar during a long run.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It is the link back to the recording: which packet, which "
            "sequence number, which time the byte came from.",
        ),
        related=("provenance",),
    ),
    # -- Framing -----------------------------------------------------------
    _e(
        "framing",
        QtCore.QT_TRANSLATE_NOOP("Help", "Framing a message"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Framing strategy"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "The rule for cutting the byte stream into messages."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Fields are described relative to the start of a message, so the "
            "boundaries must be decided before any field offset means anything.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP(
            "Help", "length_prefixed, fixed_size, marker_based, manual."
        ),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "The example rule is length_prefixed: two bytes at offset 2 give "
            "the length.",
        ),
        effect=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A wrong strategy shifts every message boundary, so every field is "
            "read from the wrong place.",
        ),
        mistakes=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Assuming packet boundaries are message boundaries. They are not: "
            "one message can span packets and one packet can hold several.",
        ),
        related=("length_offset", "length_size", "fixed_size", "marker_bytes"),
    ),
    _e(
        "length_prefixed",
        QtCore.QT_TRANSLATE_NOOP("Help", "Framing a message"),
        QtCore.QT_TRANSLATE_NOOP("Help", "length_prefixed"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Each message starts with a field that gives its own length."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Common when a protocol states how long a message is before sending it.",
        ),
        depends=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Read with length_offset, length_size, byte_order and length_covers.",
        ),
        related=("length_offset", "length_size", "length_covers"),
    ),
    _e(
        "fixed_size",
        QtCore.QT_TRANSLATE_NOOP("Help", "Framing a message"),
        QtCore.QT_TRANSLATE_NOOP("Help", "fixed_size"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Every message is the same number of bytes."),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "Used when the protocol has one message shape."
        ),
        depends=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Set the size; a stream whose length is not a multiple of it ends "
            "with an incomplete message.",
        ),
        related=("fixed_size",),
    ),
    _e(
        "marker_based",
        QtCore.QT_TRANSLATE_NOOP("Help", "Framing a message"),
        QtCore.QT_TRANSLATE_NOOP("Help", "marker_based"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Messages are separated by a start marker, an end marker, or both."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "Used when a message begins or ends with a known byte pattern."
        ),
        depends=QtCore.QT_TRANSLATE_NOOP(
            "Help", "The markers are byte patterns, not offsets."
        ),
        related=("marker_bytes",),
    ),
    _e(
        "manual",
        QtCore.QT_TRANSLATE_NOOP("Help", "Framing a message"),
        QtCore.QT_TRANSLATE_NOOP("Help", "manual"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "No automatic framing: the reader marks boundaries by hand."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A fallback while the structure is still unknown; the rule keeps "
            "only the field layout.",
        ),
        related=("framing",),
        surface=ADVANCED,
    ),
    _e(
        "length_offset",
        QtCore.QT_TRANSLATE_NOOP("Help", "Framing a message"),
        QtCore.QT_TRANSLATE_NOOP("Help", "length at offset"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Where the length field sits inside each message, counted from its start.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It tells the reader where to read the number that gives the "
            "message length.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "0 or greater. Offset 0 is the first byte of the message; counting "
            "starts at zero, not one.",
        ),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help", "Offset 2 means the third and fourth bytes of the message."
        ),
        effect=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A larger value reads the length from further into the message; if "
            "the message is shorter than offset plus size, the length cannot be "
            "read and the message is incomplete.",
        ),
        depends=QtCore.QT_TRANSLATE_NOOP(
            "Help", "Only used by the length_prefixed strategy."
        ),
        related=("length_size", "length_covers"),
    ),
    _e(
        "length_size",
        QtCore.QT_TRANSLATE_NOOP("Help", "Framing a message"),
        QtCore.QT_TRANSLATE_NOOP("Help", "length size"),
        QtCore.QT_TRANSLATE_NOOP("Help", "How many bytes the length field occupies."),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It says how wide the number is, which decides how large a message "
            "can be described.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP("Help", "1, 2 or 4 bytes."),
        default=QtCore.QT_TRANSLATE_NOOP(
            "Help", "2 bytes, enough for messages up to 65535 bytes."
        ),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "2 bytes read big-endian give a length of 21 for the bytes 0x00 0x15.",
        ),
        effect=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Too small a size truncates the length; too large reads neighbouring "
            "bytes into it.",
        ),
        depends=QtCore.QT_TRANSLATE_NOOP("Help", "Read together with byte order."),
        related=("length_offset", "byte_order"),
    ),
    _e(
        "length_covers",
        QtCore.QT_TRANSLATE_NOOP("Help", "Framing a message"),
        QtCore.QT_TRANSLATE_NOOP("Help", "length counts"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Whether the length number includes the header, the payload, or the whole "
            "message.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Protocols disagree on what the length counts, and getting it wrong "
            "offsets every message by the header size.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "The values the framing module accepts: header and payload, payload "
            "only, or the whole message.",
        ),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "If the length counts the whole message, a value of 21 means the "
            "message is 21 bytes including its two-byte length field.",
        ),
        effect=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "The wrong choice shifts every boundary by the header length, so "
            "later messages are cut in the wrong place.",
        ),
        depends=QtCore.QT_TRANSLATE_NOOP(
            "Help", "Only used by the length_prefixed strategy."
        ),
        related=("length_offset", "length_size"),
    ),
    _e(
        "message_size",
        QtCore.QT_TRANSLATE_NOOP("Help", "Framing a message"),
        QtCore.QT_TRANSLATE_NOOP("Help", "message size"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "The byte length of every message under the fixed_size strategy."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It is the single number that separates messages when they are all "
            "the same size.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP("Help", "1 or greater."),
        effect=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "If the stream length is not a multiple of the size, the trailing "
            "bytes are reported as an incomplete message rather than dropped.",
        ),
        related=("fixed_size",),
    ),
    _e(
        "marker_bytes",
        QtCore.QT_TRANSLATE_NOOP("Help", "Framing a message"),
        QtCore.QT_TRANSLATE_NOOP("Help", "start / end marker"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "The byte pattern that begins or ends a message."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "It is how messages are found when their length is not stated."
        ),
        values=QtCore.QT_TRANSLATE_NOOP(
            "Help", "A hex pattern such as hex:1B02 for the bytes 0x1B 0x02."
        ),
        effect=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A pattern that also occurs inside a message body cuts it in two; a "
            "pattern that never occurs leaves one long message.",
        ),
        related=("marker_based",),
    ),
    # -- Fields ------------------------------------------------------------
    _e(
        "field",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Field"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "A named range of bytes inside a message, with a type."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A field is the unit of interpretation: it says that these bytes "
            "mean this, and lets the rule be checked against the data.",
        ),
        related=("offset", "field_type", "size", "hypothesis_flag"),
    ),
    _e(
        "offset",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "offset"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Where a field starts, counted in bytes from the start of the message.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP("Help", "It places the field on the wire."),
        values=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "0 or greater. Counting starts at zero: offset 0 is the first byte, "
            "offset 1 the second.",
        ),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Offset 4 selects the fifth byte; on the demo message that is the "
            "parameter value.",
        ),
        effect=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A larger offset moves the field later in the message; if the offset "
            "plus the size goes past the end of the message, the field is "
            "incomplete rather than read from the next message.",
        ),
        mistakes=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Counting from one, which shifts every field by one byte; or "
            "reusing a packet-relative offset when the field is "
            "message-relative.",
        ),
        related=("size", "field_type"),
    ),
    _e(
        "size",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "length / size"),
        QtCore.QT_TRANSLATE_NOOP("Help", "How many bytes the field occupies."),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It says how wide the value is, which decides the largest value it "
            "can hold.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "For fixed types it comes from the type (uint8 is 1 byte, uint16 is "
            "2, uint32 is 4). For bytes it is set explicitly.",
        ),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A uint16 at offset 2 reads two bytes and gives a value up to 65535.",
        ),
        effect=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Too small truncates the value; too large reads neighbouring bytes "
            "into it.",
        ),
        related=("field_type", "offset"),
    ),
    _e(
        "field_type",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "type"),
        QtCore.QT_TRANSLATE_NOOP("Help", "How the field's bytes are read as a value."),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It decides whether the bytes are a number, a string of bytes, or a "
            "named value from a set.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "uint8, uint16, uint32, int8, int16, int32, float32, float64, bytes, "
            "enum, bitmask, string, array, padding, varint, tlv, checksum, "
            "computed, conditional.",
        ),
        default=QtCore.QT_TRANSLATE_NOOP("Help", "uint8, a single unsigned byte."),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A command byte read as uint8 gives 2; the same bytes read as bytes "
            "give the raw pair.",
        ),
        effect=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "The type changes the number the same bytes produce; a signed type "
            "reads the top bit as a sign, so 0xFF becomes -1.",
        ),
        related=("size", "byte_order", "enum"),
    ),
    _e(
        "uint8",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "uint8"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "One unsigned byte, read as a number from 0 to 255."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "The natural type for a command byte or a small flag."
        ),
        values=QtCore.QT_TRANSLATE_NOOP("Help", "0 to 255."),
        example=QtCore.QT_TRANSLATE_NOOP("Help", "The byte 0x02 reads as 2."),
        related=("field_type", "size"),
    ),
    _e(
        "uint16",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "uint16"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Two unsigned bytes, read as a number from 0 to 65535."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "Used for lengths, ports and small identifiers."
        ),
        values=QtCore.QT_TRANSLATE_NOOP("Help", "0 to 65535."),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help", "The bytes 0x00 0x15 read big-endian as 21."
        ),
        related=("field_type", "byte_order"),
    ),
    _e(
        "uint32",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "uint32"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Four unsigned bytes, read as a number from 0 to 4294967295."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "Used for large counters, sizes and identifiers."
        ),
        values=QtCore.QT_TRANSLATE_NOOP("Help", "0 to 4294967295."),
        related=("field_type", "byte_order"),
    ),
    _e(
        "int8",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "int8"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "One signed byte, read as a number from -128 to 127."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "Used for a value that can be negative, such as a delta."
        ),
        values=QtCore.QT_TRANSLATE_NOOP("Help", "-128 to 127."),
        example=QtCore.QT_TRANSLATE_NOOP("Help", "The byte 0xFF reads as -1."),
        related=("field_type",),
    ),
    _e(
        "int16",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "int16"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Two signed bytes, read as a number from -32768 to 32767."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "Used for a signed value wider than a byte."
        ),
        values=QtCore.QT_TRANSLATE_NOOP("Help", "-32768 to 32767."),
        related=("field_type", "byte_order"),
    ),
    _e(
        "int32",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "int32"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Four signed bytes, read as a number from -2147483648 to 2147483647.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP("Help", "Used for a wide signed value."),
        values=QtCore.QT_TRANSLATE_NOOP("Help", "-2147483648 to 2147483647."),
        related=("field_type", "byte_order"),
    ),
    _e(
        "float32",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "float32"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Four bytes read as a single-precision floating-point number."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "Used when a field carries a measurement rather than a count."
        ),
        related=("float64", "byte_order"),
    ),
    _e(
        "float64",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "float64"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Eight bytes read as a double-precision floating-point number."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "Used for a measurement that needs more precision than a float32."
        ),
        related=("float32", "byte_order"),
    ),
    _e(
        "bytes",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "bytes"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "A range of bytes kept as raw data rather than read as a number."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Used for a payload, an opaque token or a value whose meaning is "
            "not yet known.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP(
            "Help", "A fixed length set by the field's size."
        ),
        related=("size", "field_type"),
    ),
    _e(
        "bitmask",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "bitmask"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "A number whose individual bits each carry a flag."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "Used when one field packs several on/off settings."
        ),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help", "The byte 0x05 has bit 0 and bit 2 set."
        ),
        related=("field_type", "enum"),
        surface=ADVANCED,
    ),
    _e(
        "string",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "string"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Bytes read as text, usually terminated by a length or a null byte."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "Used for a name or a path inside the protocol."
        ),
        related=("field_type", "size"),
    ),
    _e(
        "array",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "array"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "A repeated group of fields whose count comes from another field."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "Used when a message carries a list of like items."
        ),
        depends=QtCore.QT_TRANSLATE_NOOP(
            "Help", "It needs the field that holds the count to be read first."
        ),
        related=("field_type", "size"),
        surface=ADVANCED,
    ),
    _e(
        "padding",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "padding"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Bytes kept only to align the next field, with no meaning."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It documents the alignment rather than leaving the bytes unexplained.",
        ),
        related=("field_type",),
        surface=ADVANCED,
    ),
    _e(
        "varint",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "varint"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A number written in a variable number of bytes, one continuation bit per "
            "byte.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "Used when small values should stay short on the wire."
        ),
        values=QtCore.QT_TRANSLATE_NOOP(
            "Help", "At most ten bytes, enough for a 64-bit value."
        ),
        related=("field_type", "tlv"),
        surface=ADVANCED,
    ),
    _e(
        "tlv",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "tlv"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A tag-length-value group: a tag, then a length, then that many bytes.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "Used for optional, self-describing attributes."
        ),
        related=("field_type", "varint"),
        surface=ADVANCED,
    ),
    _e(
        "checksum",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "checksum"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A field checked against a value computed over other bytes, not extracted.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "It lets a rule fail when the bytes do not agree with the checksum."
        ),
        related=("computed", "mismatched"),
        surface=ADVANCED,
    ),
    _e(
        "computed",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "computed"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "A field whose value is calculated rather than read from the bytes."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Used to check a derived value such as a length or a checksum "
            "against what the message actually holds.",
        ),
        related=("checksum",),
        surface=ADVANCED,
    ),
    _e(
        "conditional",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "conditional"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A field that is present only when a condition on other fields holds.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "Used for a message shape that changes with its command byte."
        ),
        depends=QtCore.QT_TRANSLATE_NOOP(
            "Help", "It is evaluated against fields read earlier in the message."
        ),
        related=("field_type", "enum"),
        surface=ADVANCED,
    ),
    _e(
        "enum",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "enum values"),
        QtCore.QT_TRANSLATE_NOOP("Help", "A named set of allowed values for a field."),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It records that a byte is one of a few known commands rather than "
            "an arbitrary number.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP(
            "Help", "name=value pairs, for example set=1, get=2."
        ),
        effect=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "An enum documents the meanings but does not by itself reject a "
            "value outside the set; that is done with expected values.",
        ),
        related=("field_type", "expected"),
        surface=ADVANCED,
    ),
    _e(
        "expected",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "expected value"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Values the field is required to take for the rule to match."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It turns a description into a check: a message whose field holds "
            "another value is reported as mismatched.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP(
            "Help", "A comma-separated list of numbers or words."
        ),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A command field with expected 2 matches only the set-parameter "
            "messages and reports the rest as counterexamples.",
        ),
        effect=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "With an expected value the rule can disagree with the data, which "
            "is what produces counterexamples; without one it matches any value.",
        ),
        related=("enum", "mismatched"),
    ),
    _e(
        "hypothesis_flag",
        QtCore.QT_TRANSLATE_NOOP("Help", "Fields"),
        QtCore.QT_TRANSLATE_NOOP("Help", "marked as a guess"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "A flag saying the field's meaning is assumed, not observed."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It keeps a guess apart from a fact so the two are never confused "
            "in the report.",
        ),
        effect=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A field marked as a guess is listed in the Hypotheses tab, where "
            "alternative readings are scored against the data.",
        ),
        related=("hypotheses_view", "hypothesis"),
    ),
    _e(
        "byte_order",
        QtCore.QT_TRANSLATE_NOOP("Help", "Values and byte order"),
        QtCore.QT_TRANSLATE_NOOP("Help", "byte order"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "The order in which the bytes of a multi-byte field are combined."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It decides whether the first byte is the most or the least "
            "significant one.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "big (most significant byte first) or little (least significant first).",
        ),
        default=QtCore.QT_TRANSLATE_NOOP("Help", "big."),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "The bytes 0x01 0x02 give 258 read big-endian and 513 read little-endian.",
        ),
        effect=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "The wrong order reverses the value; the bytes on the wire are unchanged.",
        ),
        mistakes=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Assuming the order rather than checking it against the data; a "
            "length that looks implausibly large is often a byte-order slip.",
        ),
        related=("field_type", "size"),
    ),
    # -- The rule document -------------------------------------------------
    _e(
        "rule",
        QtCore.QT_TRANSLATE_NOOP("Help", "The rule document"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Rule"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A written description of how a stream is cut into messages and what each "
            "range means.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Writing the guess down is what makes it testable over the whole "
            "capture instead of over one message.",
        ),
        related=("framing", "field", "rule_version"),
    ),
    _e(
        "rule_id",
        QtCore.QT_TRANSLATE_NOOP("Help", "The rule document"),
        QtCore.QT_TRANSLATE_NOOP("Help", "id"),
        QtCore.QT_TRANSLATE_NOOP("Help", "A short name that identifies the rule."),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "It is how results, versions and the report refer to the rule."
        ),
        example=QtCore.QT_TRANSLATE_NOOP("Help", "rule, or set_parameter_request."),
        related=("rule_version",),
    ),
    _e(
        "rule_name",
        QtCore.QT_TRANSLATE_NOOP("Help", "The rule document"),
        QtCore.QT_TRANSLATE_NOOP("Help", "name"),
        QtCore.QT_TRANSLATE_NOOP("Help", "A human-readable name for the rule."),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "It is what a reader sees in the report and the version list."
        ),
        related=("rule_id",),
    ),
    _e(
        "rule_version",
        QtCore.QT_TRANSLATE_NOOP("Help", "The rule document"),
        QtCore.QT_TRANSLATE_NOOP("Help", "version"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "A number that marks one revision of the rule."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Editing a rule makes a new version, so a result can say which "
            "revision produced it.",
        ),
        default=QtCore.QT_TRANSLATE_NOOP("Help", "1 for a new rule."),
        effect=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Raising the version marks earlier results as outdated rather than "
            "current.",
        ),
        related=("rule_id", "outdated"),
    ),
    _e(
        "scope",
        QtCore.QT_TRANSLATE_NOOP("Help", "The rule document"),
        QtCore.QT_TRANSLATE_NOOP("Help", "scope / direction"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Which part of the capture the rule applies to."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A request-only rule can be scoped to one direction so it is not "
            "applied to the replies.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP("Help", "Any direction, A_to_B or B_to_A."),
        effect=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Messages outside the scope are reported as not applicable rather "
            "than as a mismatch.",
        ),
        related=("direction",),
    ),
    _e(
        "json",
        QtCore.QT_TRANSLATE_NOOP("Help", "The rule document"),
        QtCore.QT_TRANSLATE_NOOP("Help", "JSON view"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "The rule as the plain document the application reads and writes."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "The form and the JSON are the same document, so an expert can read "
            "or edit the exact definition without a second format.",
        ),
        related=("rule",),
        surface=ADVANCED,
    ),
    _e(
        "schema_version",
        QtCore.QT_TRANSLATE_NOOP("Help", "The rule document"),
        QtCore.QT_TRANSLATE_NOOP("Help", "schema_version"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "The version of the rule document format itself."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "It lets a future format change be recognised instead of misread."
        ),
        default=QtCore.QT_TRANSLATE_NOOP("Help", "1."),
        related=("rule",),
        surface=ADVANCED,
    ),
    # -- Checking a rule ---------------------------------------------------
    _e(
        "apply_rule",
        QtCore.QT_TRANSLATE_NOOP("Help", "Checking a rule"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Apply to this message"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Run the rule over the message currently open."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "It is the first, weakest test: one message can fit by luck."
        ),
        related=("corpus_check", "matched"),
    ),
    _e(
        "corpus_check",
        QtCore.QT_TRANSLATE_NOOP("Help", "Checking a rule"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Check on the whole capture"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Run the rule over every message in the capture."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It is what turns a guess into evidence, by finding the messages "
            "that disagree.",
        ),
        related=("counterexample", "precision"),
    ),
    _e(
        "status",
        QtCore.QT_TRANSLATE_NOOP("Help", "Checking a rule"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Status"),
        QtCore.QT_TRANSLATE_NOOP("Help", "The verdict of a rule on one message."),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It says how the message stood up to the rule, and it is shown as "
            "a word as well as a colour.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "matched, mismatched, incomplete, ambiguous, uncovered, "
            "not_applicable, outdated, unknown.",
        ),
        related=("matched", "mismatched", "incomplete", "ambiguous", "outdated"),
    ),
    _e(
        "matched",
        QtCore.QT_TRANSLATE_NOOP("Help", "Checking a rule"),
        QtCore.QT_TRANSLATE_NOOP("Help", "matched"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "The rule passed every formal check on the message."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A match is support for the rule on this message, not proof of the "
            "field's meaning.",
        ),
        related=("precision",),
    ),
    _e(
        "mismatched",
        QtCore.QT_TRANSLATE_NOOP("Help", "Checking a rule"),
        QtCore.QT_TRANSLATE_NOOP("Help", "mismatched"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "The rule was not satisfied on the message, for example an expected value "
            "did not hold.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A mismatch is evidence against the rule and becomes a counterexample.",
        ),
        related=("counterexample", "expected"),
    ),
    _e(
        "incomplete",
        QtCore.QT_TRANSLATE_NOOP("Help", "Checking a rule"),
        QtCore.QT_TRANSLATE_NOOP("Help", "incomplete"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "The message could not be read to the end, or the field's range crosses a "
            "gap in the stream.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It marks where the data is not enough to judge, so the message is "
            "not counted as a match.",
        ),
        related=("gap",),
    ),
    _e(
        "ambiguous",
        QtCore.QT_TRANSLATE_NOOP("Help", "Checking a rule"),
        QtCore.QT_TRANSLATE_NOOP("Help", "ambiguous"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "The field's range falls in a region where two overlapping segments "
            "disagree.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It says the bytes themselves are in question, so no verdict is given.",
        ),
        related=("ambiguity",),
    ),
    _e(
        "uncovered",
        QtCore.QT_TRANSLATE_NOOP("Help", "Checking a rule"),
        QtCore.QT_TRANSLATE_NOOP("Help", "uncovered"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Bytes of the stream that the rule does not describe."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It shows how much of the stream the framing and fields leave unexplained.",
        ),
        related=("coverage",),
    ),
    _e(
        "not_applicable",
        QtCore.QT_TRANSLATE_NOOP("Help", "Checking a rule"),
        QtCore.QT_TRANSLATE_NOOP("Help", "not_applicable"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "The rule does not apply to the message, for example another direction.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It keeps a scoped rule from reporting the other direction as a failure.",
        ),
        related=("scope",),
    ),
    _e(
        "outdated",
        QtCore.QT_TRANSLATE_NOOP("Help", "Checking a rule"),
        QtCore.QT_TRANSLATE_NOOP("Help", "outdated"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "A result produced by an earlier version of the rule."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "It stops an old result being read as if it were the current one."
        ),
        related=("rule_version",),
    ),
    _e(
        "unknown",
        QtCore.QT_TRANSLATE_NOOP("Help", "Checking a rule"),
        QtCore.QT_TRANSLATE_NOOP("Help", "unknown"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "There was not enough information to reach a verdict."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "It is the honest answer when the data does not decide."
        ),
        related=("incomplete",),
    ),
    # -- Reading the results ----------------------------------------------
    _e(
        "counterexample",
        QtCore.QT_TRANSLATE_NOOP("Help", "Reading the results"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Counterexample"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "A concrete message on which the rule did not hold."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It is the evidence against the rule, and it comes with the exact "
            "message it was found in so the bytes can be checked.",
        ),
        related=("mismatched", "corpus_check"),
    ),
    _e(
        "precision",
        QtCore.QT_TRANSLATE_NOOP("Help", "Reading the results"),
        QtCore.QT_TRANSLATE_NOOP("Help", "precision"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Matched messages divided by applicable messages."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It measures how often the rule agreed where it applied, over this "
            "capture only.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP("Help", "A ratio from 0 to 1."),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help", "205 matched out of 217 applicable gives a precision of about 0.94."
        ),
        depends=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It depends on the capture it was measured over; a high value on a "
            "small capture is not a proof of the protocol.",
        ),
        related=("coverage", "matched", "mismatched"),
    ),
    _e(
        "coverage",
        QtCore.QT_TRANSLATE_NOOP("Help", "Reading the results"),
        QtCore.QT_TRANSLATE_NOOP("Help", "coverage"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Applicable messages divided by all framed messages."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "It measures how much of the capture the rule's scope reached."
        ),
        values=QtCore.QT_TRANSLATE_NOOP("Help", "A ratio from 0 to 1."),
        depends=QtCore.QT_TRANSLATE_NOOP(
            "Help", "A rule scoped to one direction has a low coverage by design."
        ),
        related=("precision", "not_applicable"),
    ),
    _e(
        "fragmentation",
        QtCore.QT_TRANSLATE_NOOP("Help", "Reading the results"),
        QtCore.QT_TRANSLATE_NOOP("Help", "fragmentation"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Messages divided by sessions: how many messages a session holds on average.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It is a property of the capture, not of the rule; it tells the "
            "reader how much data the measurement rests on.",
        ),
        values=QtCore.QT_TRANSLATE_NOOP("Help", "A count of messages per session."),
        related=("session", "message"),
    ),
    _e(
        "counterexample_density",
        QtCore.QT_TRANSLATE_NOOP("Help", "Reading the results"),
        QtCore.QT_TRANSLATE_NOOP("Help", "counterexample density"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Counterexamples per applicable message."),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "It measures how often the rule fails where it applies."
        ),
        values=QtCore.QT_TRANSLATE_NOOP("Help", "A count per applicable message."),
        related=("counterexample", "precision"),
    ),
    _e(
        "unknown_ratio",
        QtCore.QT_TRANSLATE_NOOP("Help", "Reading the results"),
        QtCore.QT_TRANSLATE_NOOP("Help", "unknown ratio"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Unknown messages divided by all messages."),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "It shows how much of the capture could not be judged."
        ),
        values=QtCore.QT_TRANSLATE_NOOP("Help", "A ratio from 0 to 1."),
        related=("unknown",),
    ),
    _e(
        "uncovered_ratio",
        QtCore.QT_TRANSLATE_NOOP("Help", "Reading the results"),
        QtCore.QT_TRANSLATE_NOOP("Help", "uncovered ratio"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Stream bytes not covered by the rule, divided by all stream bytes."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "It shows how much of the stream the rule leaves unexplained."
        ),
        values=QtCore.QT_TRANSLATE_NOOP("Help", "A ratio from 0 to 1."),
        related=("uncovered",),
    ),
    _e(
        "constant",
        QtCore.QT_TRANSLATE_NOOP("Help", "Reading the results"),
        QtCore.QT_TRANSLATE_NOOP("Help", "constant"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A candidate reading in which the field never varies across the corpus.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A field that is always the same is a candidate for a fixed marker "
            "or a protocol version.",
        ),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A field that is 2 in every message of the corpus is reported as "
            "constant 2.",
        ),
        related=("counter", "hypotheses_view"),
        surface=ADVANCED,
    ),
    _e(
        "counter",
        QtCore.QT_TRANSLATE_NOOP("Help", "Reading the results"),
        QtCore.QT_TRANSLATE_NOOP("Help", "counter"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A candidate reading in which the field advances by a fixed amount between "
            "successive messages.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "A field that steps evenly is a candidate for a sequence number."
        ),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "A field that rises by one each message is reported as advancing by "
            "1 between messages.",
        ),
        depends=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It is measured in message order, so it depends on the order the "
            "messages were framed in.",
        ),
        related=("constant", "hypotheses_view"),
        surface=ADVANCED,
    ),
    # -- Everyday concepts -------------------------------------------------
    _e(
        "offset_concept",
        QtCore.QT_TRANSLATE_NOOP("Help", "Everyday concepts"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Offset"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "A position counted in bytes from a fixed starting point."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Offsets are how the rule says where a field is; the start point "
            "must always be named, because a packet-relative and a "
            "message-relative offset are different numbers.",
        ),
        example=QtCore.QT_TRANSLATE_NOOP(
            "Help", "Offset 2 in a message is the third byte of that message."
        ),
        related=("offset",),
    ),
    _e(
        "hex",
        QtCore.QT_TRANSLATE_NOOP("Help", "Everyday concepts"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Hex"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Base-16 notation, one pair of digits per byte."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It shows the exact bytes without the ambiguity of printable characters.",
        ),
        example=QtCore.QT_TRANSLATE_NOOP("Help", "0x0f is the byte 15."),
        related=("hex_view",),
    ),
    _e(
        "ascii",
        QtCore.QT_TRANSLATE_NOOP("Help", "Everyday concepts"),
        QtCore.QT_TRANSLATE_NOOP("Help", "ASCII"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "The same bytes shown as printable characters where they are printable.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help", "It makes text inside a binary protocol visible at a glance."
        ),
        related=("hex_view",),
    ),
    _e(
        "provenance",
        QtCore.QT_TRANSLATE_NOOP("Help", "Everyday concepts"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Provenance"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "The record of which packet, sequence number and time each byte came from.",
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It is the link back to the recording, so any claim can be traced "
            "to its evidence.",
        ),
        related=("status_bar", "gap"),
    ),
    _e(
        "gap",
        QtCore.QT_TRANSLATE_NOOP("Help", "Everyday concepts"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Gap"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "A range of the stream that was never captured."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It is marked as a gap rather than filled with zeros, so a "
            "half-read message is never mistaken for a complete one.",
        ),
        related=("incomplete", "provenance"),
    ),
    _e(
        "ambiguity",
        QtCore.QT_TRANSLATE_NOOP("Help", "Everyday concepts"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Ambiguity"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "A region where two overlapping segments carry different bytes."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It marks data that is genuinely in question, so no verdict is "
            "given over it.",
        ),
        related=("ambiguous",),
    ),
    _e(
        "hypothesis",
        QtCore.QT_TRANSLATE_NOOP("Help", "Everyday concepts"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Hypothesis"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "A statement about the protocol that is not yet checked."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It is the middle step between an observation and a rule: a guess "
            "written down so it can be tested.",
        ),
        related=("hypothesis_flag", "counterexample"),
    ),
    _e(
        "observation",
        QtCore.QT_TRANSLATE_NOOP("Help", "Everyday concepts"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Observation"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "Something the data shows directly, such as the value of a byte."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "Observations are kept apart from guesses so the report never "
            "presents one as the other.",
        ),
        related=("hypothesis",),
    ),
    _e(
        "report",
        QtCore.QT_TRANSLATE_NOOP("Help", "Everyday concepts"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Report"),
        QtCore.QT_TRANSLATE_NOOP("Help", "The written result of the investigation."),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It states what was checked, on which data, and what was not, so "
            "the work can be reproduced and reviewed.",
        ),
        related=("report_view",),
    ),
    _e(
        "tutor",
        QtCore.QT_TRANSLATE_NOOP("Help", "Everyday concepts"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Tutor panel"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "The strip that walks through the course one step at a time."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It shows the current lesson, points at the element it is talking "
            "about, and waits for the real action before moving on.",
        ),
        related=("learning_mode", "learning_centre"),
    ),
    _e(
        "learning_centre",
        QtCore.QT_TRANSLATE_NOOP("Help", "Everyday concepts"),
        QtCore.QT_TRANSLATE_NOOP("Help", "Learning centre"),
        QtCore.QT_TRANSLATE_NOOP(
            "Help", "The window for choosing a lesson or looking a term up."
        ),
        purpose=QtCore.QT_TRANSLATE_NOOP(
            "Help",
            "It lets a reader start the course, continue it, pick a single "
            "lesson, search the reference or reset their progress.",
        ),
        related=("tutor", "learning_mode"),
    ),
)

ENTRY_BY_KEY: dict[str, HelpEntry] = {entry.key: entry for entry in HELP_ENTRIES}


def translate(text: str, context: str = HELP_CONTEXT) -> str:
    """Translate a catalogue string that was stored untranslated."""
    return QtCore.QCoreApplication.translate(context, text)


def lookup(key: str) -> HelpEntry | None:
    """Return the entry for *key*, or ``None`` when there is none."""
    return ENTRY_BY_KEY.get(key)


def search(query: str) -> list[HelpEntry]:
    """Return the entries whose text contains *query*, case-insensitively.

    Matching is done on the English source strings, so the search works the same
    in either interface language and does not depend on a translation.
    """
    needle = query.strip().lower()
    if not needle:
        return list(HELP_ENTRIES)
    found: list[HelpEntry] = []
    for entry in HELP_ENTRIES:
        haystack = " ".join(
            [entry.key, entry.title, entry.summary, entry.purpose, entry.example]
        ).lower()
        if needle in haystack:
            found.append(entry)
    return found


def entries_for_section(section: str) -> list[HelpEntry]:
    """Return the entries in *section*."""
    return [entry for entry in HELP_ENTRIES if entry.section == section]
