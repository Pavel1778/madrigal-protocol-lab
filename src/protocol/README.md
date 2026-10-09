# Protocol and hypothesis engine

Statuses, framing strategies, rule format, corpus verification, versioning, and
the command line interface for replaying a rule against a normalized capture.

## Statuses

A message (or a single field) is classified with one of:

| Status           | Meaning                                                              |
| ---------------- | -------------------------------------------------------------------- |
| `matched`        | Framing and every declared field read consistently with the rule.    |
| `mismatched`     | A field value contradicts the rule (for example an `expected` value).|
| `incomplete`     | The message or a field crosses a gap or the end of the stream.       |
| `ambiguous`      | A field range overlaps contradictory bytes reported by reassembly.   |
| `uncovered`      | No declared field is present in this message.                        |
| `not_applicable` | The rule scope excludes this direction.                              |
| `outdated`       | The result was produced by an older rule version.                    |
| `unknown`        | Reserved.                                                            |

`matched` means "consistent with the rule over the messages that were tested".
It is not proof: a rule that fits the observed messages can still be contradicted
by a wider corpus, which is why counterexamples are collected explicitly.

## Framing

`src/protocol/framing.py` turns a flat directional stream into candidate
messages. TCP packet boundaries are not message boundaries; a message split
across two packets is one message.

- `length_prefixed` — a length field at `length_offset` (`length_size` bytes,
  `byte_order`) gives the message length. `length_covers` says what the length
  value counts:
  - `payload` (default when the field is absent) — only the payload; total =
    `length_offset + length_size + value`;
  - `payload_and_length_field` — the payload plus the length field; total =
    `length_offset + value`;
  - `entire_message` — the whole message; total = `value`.
  The deprecated boolean `length_includes_payload` is still accepted:
  `true` maps to `entire_message`, `false` maps to `payload`.
- `fixed_size` — every message is `size` bytes; a short final message is
  `incomplete`.
- `marker_based` — messages are delimited by `start_bytes` and `end_bytes`.
- `manual` — an explicit list of `{offset, length}` ranges.

## Rule format

A rule is JSON or YAML. The machine-readable definition is
`docs/schemas/rule.schema.json`. Example (`src/protocol/examples/`):

```json
{
  "schema_version": 1,
  "rule_id": "set_parameter_request",
  "rule_version": 1,
  "scope": { "direction": "A_to_B" },
  "framing": {
    "type": "length_prefixed",
    "length_offset": 2,
    "length_size": 2,
    "byte_order": "big",
    "length_covers": "entire_message"
  },
  "fields": [
    { "name": "command", "offset": 0, "type": "uint8", "expected": [4] },
    { "name": "parameter_value", "offset": 4, "type": "uint16", "byte_order": "big", "hypothesis": true }
  ]
}
```

Field types: `uint8`, `uint16`, `uint32`, `int8`, `int16`, `int32`, `bytes`,
`enum`. `expected` lists allowed values; a value outside the list is
`mismatched`. `hypothesis: true` marks a field whose meaning is an assumption.
`missing_ok: true` lets a field be absent without failing the message.

## Command line

```
python -m src.protocol.cli apply  --rule rule.json --capture normalized.json --out result.json
python -m src.protocol.cli verify --rule rule.json --capture normalized.json --out report.json
```

`apply` writes a result in the contract format (`docs/schemas/result.schema.json`).
`verify` applies the rule to every stream of the capture and writes a report with
per-status counts and the counterexamples.

## Versioning

Editing a rule that changes framing or field reading produces a new
`rule_version`. Results from older versions become `outdated`
(`src/hypothesis/versioning.py`). Re-checking the corpus after an edit yields a
`VersionComparison` listing counterexamples the new version `resolved` and any it
`introduced`. Bytes are never rewritten by a rule change.

## Output paths

- `src/protocol/` — `stream.py`, `framing.py`, `rule.py`, `engine.py`,
  `result.py`, `cli.py`, `examples/`
- `src/hypothesis/` — `status.py`, `corpus.py`, `versioning.py`
- `tests/protocol/`, `tests/hypothesis/`
