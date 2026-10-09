"""Status vocabulary shared by the rule engine and the hypothesis engine.

The statuses separate an observation from an assumption and a verified fact
from an open question. "Confirmed within the tested domain" is not the same as
"proven": a ``matched`` message only means the rule read the bytes consistently
with its declared layout, over the messages that were actually tested.
"""

from __future__ import annotations

from enum import Enum


class Status(str, Enum):
    MATCHED = "matched"
    MISMATCHED = "mismatched"
    INCOMPLETE = "incomplete"
    AMBIGUOUS = "ambiguous"
    UNCOVERED = "uncovered"
    NOT_APPLICABLE = "not_applicable"
    OUTDATED = "outdated"
    UNKNOWN = "unknown"


#: The six core statuses used for message-level classification.
CORE_STATUSES = (
    Status.MATCHED,
    Status.MISMATCHED,
    Status.INCOMPLETE,
    Status.AMBIGUOUS,
    Status.UNCOVERED,
    Status.NOT_APPLICABLE,
)

ALL_STATUSES = tuple(Status)

#: Statuses that count as "(partly) explained" when summarising a corpus.
EXPLAINED = frozenset({Status.MATCHED, Status.AMBIGUOUS})

#: Statuses that carry evidence against a rule.
CONTRA_STATUSES = frozenset({Status.MISMATCHED, Status.INCOMPLETE, Status.UNCOVERED})
