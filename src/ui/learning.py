"""The interactive course that teaches Madrigal from the first launch.

The course is data, not a set of hand-written dialogs: a list of lessons, each
one a short sequence of steps, and each step a single instruction with an
optional pointer at a real widget and a real completion test. The tutor panel
renders the lesson currently selected; the window owns the state the completion
tests read, so the course advances only when the action was actually performed
in the application, never because a button was pressed.

Strings are kept as English source literals inside ``QT_TRANSLATE_NOOP`` markers
so ``pyside6-lupdate`` can harvest them from this data module, and translated at
render time with :func:`QCoreApplication.translate`. A lesson built at import
time must not freeze the language it happened to start in.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from PySide6 import QtCore

# Translation contexts. One per catalogue family so a translator sees the course
# text and the reference text apart.
LESSON_CONTEXT = "Learning"


@dataclass(frozen=True)
class Step:
    """One instruction inside a lesson.

    ``requires`` is the name of a state the window must reach before the step is
    considered done. ``None`` means the step is informative and can be left with
    ``Next`` straight away. ``target`` names a widget the tutor points at.
    """

    text: str
    why: str
    target: str | None = None
    requires: str | None = None
    show_me: str | None = None


@dataclass(frozen=True)
class Lesson:
    """A titled sequence of steps, optionally with background notes."""

    key: str
    title: str
    intro: str
    steps: tuple[Step, ...]
    theory: tuple[str, ...] = field(default_factory=tuple)


def _s(
    text: str,
    why: str,
    target: str | None = None,
    requires: str | None = None,
    show_me: str | None = None,
) -> Step:
    return Step(
        QtCore.QT_TRANSLATE_NOOP("Learning", text),
        QtCore.QT_TRANSLATE_NOOP("Learning", why),
        target,
        requires,
        show_me,
    )


def _l(
    key: str, title: str, intro: str, steps: Iterable[Step], theory: Iterable[str] = ()
) -> Lesson:
    return Lesson(
        key=key,
        title=QtCore.QT_TRANSLATE_NOOP("Learning", title),
        intro=QtCore.QT_TRANSLATE_NOOP("Learning", intro),
        steps=tuple(steps),
        theory=tuple(QtCore.QT_TRANSLATE_NOOP("Learning", item) for item in theory),
    )


# The course. The order is the order a first-time reader should follow: what the
# tool is for, then the demo data, then the areas of the window, then the work
# itself, ending with a task they do without being walked through it.
LESSONS: tuple[Lesson, ...] = (
    _l(
        "welcome",
        QtCore.QT_TRANSLATE_NOOP("Learning", "What Madrigal is for"),
        QtCore.QT_TRANSLATE_NOOP(
            "Learning", "A laboratory for reading a protocol nobody has documented yet."
        ),
        [
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "A protocol is an agreement about how two programs talk. When "
                    "nobody wrote it down, the only record left is the bytes that "
                    "crossed the wire.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Madrigal exists to turn those bytes into a description you can "
                    "check, instead of a guess you have to trust.",
                ),
            ),
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "A recording is the traffic a machine saw. A session is one "
                    "conversation inside it, and a message is one thing said in that "
                    "conversation.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Keeping these three apart is what makes the rest of the work "
                    "possible: you always know which message a byte belongs to.",
                ),
            ),
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "You will not prove a protocol in one pass. You form a guess, "
                    "write it down as a rule, run it over the recording, and look "
                    "for the messages that break it.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "A rule that survives every message is still only as good as the "
                    "data you tested it on; Madrigal shows that limit instead of "
                    "hiding it.",
                ),
            ),
        ],
    ),
    _l(
        "load",
        QtCore.QT_TRANSLATE_NOOP("Learning", "Open the example recording"),
        QtCore.QT_TRANSLATE_NOOP(
            "Learning",
            "The tool ships with a small investigation you can follow end to end.",
        ),
        [
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Open the built-in example. A recording and a first rule appear, "
                    "so there is something real on screen to work with.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Starting from a real capture means every number later is a real "
                    "measurement, not a demonstration value.",
                ),
                target="session_tree",
                requires="capture_open",
                show_me="open_demo",
            ),
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "The list on the left now holds the conversations found in the "
                    "recording. Each row is one session.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "A capture usually holds several conversations at once; the list "
                    "is how you choose the one to study.",
                ),
                target="session_tree",
                requires="capture_open",
            ),
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Pick a conversation, then choose which way the data flowed, "
                    "A to B or B to A.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "A protocol is not symmetric: the request and the reply are read "
                    "apart, so the direction matters.",
                ),
                target="direction_combo",
                requires="direction_chosen",
                show_me="select_direction",
            ),
        ],
    ),
    _l(
        "interface",
        QtCore.QT_TRANSLATE_NOOP("Learning", "Find your way around the window"),
        QtCore.QT_TRANSLATE_NOOP(
            "Learning",
            "Three columns: what was said, the bytes, and what they might mean.",
        ),
        [
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "The left column is the recording: sessions, directions and "
                    "messages.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "You choose what to look at here; everything else follows the "
                    "choice.",
                ),
                target="sessions_box",
            ),
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "The centre is the bytes themselves: offset, hex and ASCII for "
                    "the selected message.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "This is the ground truth. Every interpretation is checked "
                    "against these bytes.",
                ),
                target="hex_view",
            ),
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "The right column is the analysis: interpretation, comparison, "
                    "hypotheses, the report and the version diff.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "These are the tools for turning bytes into a claim, and for "
                    "checking the claim.",
                ),
                target="right_tabs",
            ),
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "The bottom line shows where the byte under the cursor came from: "
                    "which packet, which sequence number, which time.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "This is the link back to the recording, so a claim can always be "
                    "traced to its evidence.",
                ),
                target="status_bar",
            ),
        ],
    ),
    _l(
        "bytes",
        QtCore.QT_TRANSLATE_NOOP("Learning", "Read the bytes"),
        QtCore.QT_TRANSLATE_NOOP(
            "Learning", "Offset, hex and ASCII, and why one message is not enough."
        ),
        [
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Click a byte in the centre. Its offset, its value and the packet "
                    "it came from appear in the status line.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Reading the raw bytes is the observation everything else is "
                    "built on.",
                ),
                target="hex_view",
                requires="byte_selected",
            ),
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Drag across a range of bytes. A multi-byte field is read as one "
                    "value; the range is what a field in a rule will describe.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "A field is a range with a meaning, so selecting the range is the "
                    "first half of describing it.",
                ),
                target="hex_view",
                requires="byte_selected",
            ),
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "The colour behind a byte is the verdict of the rule you have "
                    "applied: green agrees, red disagrees, amber is undecided.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "The colour is a status, not decoration, and the same status is "
                    "also written in words so it does not depend on seeing colour.",
                ),
                target="hex_view",
            ),
        ],
    ),
    _l(
        "structure",
        QtCore.QT_TRANSLATE_NOOP("Learning", "Look for structure"),
        QtCore.QT_TRANSLATE_NOOP(
            "Learning",
            "Similar messages side by side are how a pattern becomes visible.",
        ),
        [
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Open the Compare tab and put two messages next to each other.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "What stays the same between messages is a candidate for a "
                    "constant field; what changes is a candidate for a value.",
                ),
                target="right_tabs",
                requires="compare_open",
                show_me="show_compare",
            ),
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "The Hypotheses tab lists what the tool has noticed about the "
                    "messages so far.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "These are observations, not conclusions: they are places to look, "
                    "not answers.",
                ),
                target="right_tabs",
            ),
        ],
    ),
    _l(
        "hypothesis",
        QtCore.QT_TRANSLATE_NOOP("Learning", "From a range to a field"),
        QtCore.QT_TRANSLATE_NOOP(
            "Learning", "A guess about a byte range becomes a line in a rule."
        ),
        [
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "With a range selected, build a rule. The range is offered as the "
                    "first field.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Writing the guess down is what makes it testable: a hunch you "
                    "cannot run over the data is not yet a hypothesis.",
                ),
                target="hex_view",
                requires="rule_open",
                show_me="build_rule",
            ),
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Name the field and choose its type and size, then mark it as a "
                    "guess if you are not sure yet.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "A field marked as a guess is kept apart from an observed fact, "
                    "so the two are never confused later.",
                ),
                target="right_tabs",
            ),
        ],
    ),
    _l(
        "rule",
        QtCore.QT_TRANSLATE_NOOP("Learning", "Build and apply the rule"),
        QtCore.QT_TRANSLATE_NOOP(
            "Learning",
            "The rule describes how the stream is cut up and what each range means.",
        ),
        [
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "In the rule form, say how messages are separated: by a length, "
                    "by a fixed size, or by a marker.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Framing decides where one message ends and the next begins; get "
                    "it wrong and every field offset is wrong with it.",
                ),
                target="right_tabs",
                requires="rule_open",
                show_me="build_rule",
            ),
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Apply the rule. The bytes are annotated with the verdict for "
                    "each field.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Applying it to the message in front of you is the first, weakest "
                    "test: one message can always fit by luck.",
                ),
                target="right_tabs",
                requires="rule_applied",
                show_me="apply_rule",
            ),
        ],
    ),
    _l(
        "verify",
        QtCore.QT_TRANSLATE_NOOP("Learning", "Check it on all the data"),
        QtCore.QT_TRANSLATE_NOOP(
            "Learning",
            "A rule that fits one message is not yet a rule that fits the protocol.",
        ),
        [
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Run the rule over the whole capture, not just the open message.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "The messages that disagree are the useful ones: they say where "
                    "the guess is too narrow.",
                ),
                target="right_tabs",
                requires="corpus_applied",
                show_me="apply_to_capture",
            ),
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Read the counts: how many messages matched, how many did not, "
                    "how many were too short to judge.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "A count is a measurement over this capture only; the panel says "
                    "so rather than calling the rule proven.",
                ),
                target="right_tabs",
                requires="corpus_applied",
            ),
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Open a counterexample. The bytes that disagree are highlighted "
                    "in the centre.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "A counterexample is concrete evidence against the rule, and it "
                    "comes with the exact message it was found in.",
                ),
                target="validation_view",
                requires="corpus_applied",
            ),
        ],
    ),
    _l(
        "refine",
        QtCore.QT_TRANSLATE_NOOP("Learning", "Refine the guess"),
        QtCore.QT_TRANSLATE_NOOP(
            "Learning", "Change the rule, run it again, and compare the two attempts."
        ),
        [
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Edit the rule to account for the counterexample, then apply it "
                    "again.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Refining is the actual work of the laboratory; the first rule is "
                    "a starting point, not an answer.",
                ),
                target="right_tabs",
                requires="rule_applied",
            ),
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Use the version diff to see what changed between the two runs.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Comparing attempts shows whether the change helped, and where "
                    "the remaining disagreements are.",
                ),
                target="right_tabs",
                requires="rule_applied",
            ),
        ],
    ),
    _l(
        "reports",
        QtCore.QT_TRANSLATE_NOOP("Learning", "Reports and the expert tools"),
        QtCore.QT_TRANSLATE_NOOP(
            "Learning",
            "Everything the investigation produced, in a form you can hand over.",
        ),
        [
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "The Report tab gathers the hypotheses, the examples, the "
                    "counterexamples and the open questions.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "The report is the result of the work, written so a reader who "
                    "was not here can follow it.",
                ),
                target="right_tabs",
            ),
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "The Timeline shows when each message was sent, and the version "
                    "diff compares two rules.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Time and history are evidence too: they show how a claim was "
                    "reached and changed.",
                ),
                target="right_tabs",
            ),
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "The rule is plain JSON. In the expert mode you can read and edit "
                    "it directly.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "The form and the JSON are the same document, so an expert is "
                    "never locked out of the exact definition.",
                ),
                target="right_tabs",
            ),
        ],
    ),
    _l(
        "practice",
        QtCore.QT_TRANSLATE_NOOP("Learning", "Your turn"),
        QtCore.QT_TRANSLATE_NOOP(
            "Learning", "Do the whole loop once without being walked through it."
        ),
        [
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Open a message you have not looked at, select a range you think "
                    "is a field, and build a rule from it.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Doing it unaided is the point of the course; the hints stay "
                    "available if you want them.",
                ),
                target="hex_view",
                requires="rule_open",
            ),
            _s(
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Apply the rule, then run it over the whole capture and look for a "
                    "message that disagrees.",
                ),
                QtCore.QT_TRANSLATE_NOOP(
                    "Learning",
                    "Finishing the loop on your own data is the skill the course was "
                    "teaching.",
                ),
                target="right_tabs",
                requires="corpus_applied",
            ),
        ],
    ),
)

LESSON_BY_KEY: dict[str, Lesson] = {lesson.key: lesson for lesson in LESSONS}

# The five core lessons the short workflow strip walks through. The remaining
# lessons are reachable from the learning centre.
CORE_KEYS: tuple[str, ...] = ("load", "rule", "verify", "refine", "reports")


def lesson_index(key: str) -> int:
    """Return the position of the lesson with *key*, or ``0`` when unknown."""
    for index, lesson in enumerate(LESSONS):
        if lesson.key == key:
            return index
    return 0


def translate(text: str, context: str = LESSON_CONTEXT) -> str:
    """Translate a course string that was stored untranslated."""
    return QtCore.QCoreApplication.translate(context, text)


# A completion test: given the window, has the state the step asks for been
# reached? The window supplies the mapping so this module never imports it.
StateTest = Callable[[object], bool]
