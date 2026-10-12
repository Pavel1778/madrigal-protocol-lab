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
    "ApplicationResult",
    "Capture",
    "CaptureError",
    "Counterexample",
    "DirectionalStream",
    "FieldResult",
    "FieldSpec",
    "FramingError",
    "FramingStrategy",
    "Hole",
    "Message",
    "MessageResult",
    "Rule",
    "RuleError",
    "apply_rule",
    "apply_rule_fields",
    "build_result",
    "capture_from_dict",
    "flatten_fields",
    "frame_stream",
    "load_capture",
    "load_rule",
    "parse_rule",
    "summarise",
    "write_result",
]

