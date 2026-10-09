"""Protocol engine: framing, declarative rules and rule application."""

from .engine import (
    Counterexample,
    FieldResult,
    MessageResult,
    apply_rule,
    apply_rule_fields,
    flatten_fields,
)
from .framing import FramingError, FramingStrategy, Message, frame_stream
from .result import ApplicationResult, build_result, summarise, write_result
from .rule import FieldSpec, Rule, RuleError, load_rule, parse_rule
from .stream import (
    Capture,
    CaptureError,
    DirectionalStream,
    Hole,
    capture_from_dict,
    load_capture,
)

__all__ = [
    "Message",
    "FramingStrategy",
    "FramingError",
    "frame_stream",
    "FieldSpec",
    "Rule",
    "RuleError",
    "parse_rule",
    "load_rule",
    "FieldResult",
    "MessageResult",
    "Counterexample",
    "apply_rule",
    "apply_rule_fields",
    "flatten_fields",
    "ApplicationResult",
    "build_result",
    "summarise",
    "write_result",
    "DirectionalStream",
    "Hole",
    "Capture",
    "CaptureError",
    "capture_from_dict",
    "load_capture",
]

