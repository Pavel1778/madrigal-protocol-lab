# Slide verification

Every numeric claim on the deck is checked against the code that produced it, so
a reviewer can move from a sentence on a slide to the evidence behind it. The
deck is `presentation/slides.md`; the rendered pages are `presentation/slides.pdf`
(nineteen pages). Where a slide quotes a number, the number is stated here with
the command that reproduces it. Everything below comes from `docs/METRICS.md`
and `docs/AUDIT.md`.

## Постановка и метод

### Slide 3 — Границы пакета и сообщения

No numeric claim. TCP delivers a byte stream; a message boundary is a property of
the protocol, not of the packet (`src/protocol/framing.py`).

### Slide 5 — Смещение поля длины

No numeric claim. One rule, two readings: the length field stays at offset 2
while the frame boundary moves four bytes later. The worked example is the byte
string `01 00 00 03 13 00 55`.

### Slide 6 — Архитектура

No numeric claim. Four modules (`src/capture`, `src/protocol`, `src/hypothesis`,
`src/ui`) exchange JSON documents validated against JSON Schema draft 2020-12
(`docs/schemas/`); the call order does not matter.

## Реализация

### Slide 7 — Происхождение байта

| claim | evidence |
| --- | --- |
| provenance carries packet index, sequence number and timestamp | `src/capture/` provenance records; shown live on `screenshots/09_provenance.png` |
| a missing packet becomes a gap, not zero bytes | `screenshots/04_hex_gap.png`; `docs/AUDIT.md` |

### Slide 8 — Правила и фрейминг

| claim | evidence |
| --- | --- |
| four framing families | `src/protocol/framing.py`: length-prefixed, fixed-size, delimiter, manual |
| six field types | `src/protocol/fields.py`: uint, bytes, enum, string, checksum, computed |
| `hypothesis` marks a guess about meaning | field flag in `docs/schemas/rule.schema.json` |

### Slide 9 — Контрпример важнее метрики

| claim | evidence |
| --- | --- |
| six per-message statuses | `src/hypothesis/result.py`: matched, mismatched, incomplete, ambiguous, uncovered, not_applicable |
| counterexample byte: `s2` / `A_to_B`, offset 0, bytes `02 00 00 03 13 00 55` | `verify` output, `contradictions[0]` |
| 80 v1 mismatches sit on offset 0 in `s2` and `s3` | the same `verify` output: 60 `value 2 not in expected [1]`, 20 `value 3 not in expected [1]` |
| meaning outside the proposed set is never proposed | `src/hypothesis/alternatives.py` |

## Результаты

### Slide 11 — Уточнение правила

| claim | evidence |
| --- | --- |
| v1: 60 matched, 80 mismatched | `python -m src.protocol.cli verify --rule examples/corpus_rule_v1.json --capture tests/corpus/reference_export/corpus_capture_01.normalized.json` |
| v2: 140 matched, 0 mismatched | `python -m src.protocol.cli verify` with the v2 rule |
| precision v1 0.43, v2 1.00 | `docs/METRICS.md`, `docs/RULE_V1_V2.md` |
| only the command set changes `[1]` → `[1, 2, 3]` | `git diff` between the two rule files; `docs/RULE_V1_V2.md` |
| an old result keeps its version and becomes `outdated` | `screenshots/08_diff.png` |

### Slide 12 — Покрытие корпуса организаторов

| claim | evidence |
| --- | --- |
| 90 messages: 45 requests + 45 responses, all matched | `docs/METRICS.md`, `docs/CORPUS_ANALYSIS.md` |
| the organizers' corpus was not used to refine the rule | `docs/REFERENCE_INVESTIGATION.md` |

### Slide 13 — Ресурсы

| claim | evidence |
| --- | --- |
| 95.66 MiB in 12 s, 250 000 packets, 1000 sessions | `docs/METRICS.md` |
| peak memory 350 MiB against a 4 GiB budget | `docs/METRICS.md` memory sweep |
| streaming stays below regular at 10/50/95 MiB | `docs/METRICS.md` memory sweep |

## Границы и итог

### Slide 18 — Что мы не утверждаем

| claim | evidence |
| --- | --- |
| flags byte constant (`0x00`), no reading separable | `docs/CORPUS_ANALYSIS.md` section 3 |
| value field unexplained, stays a hypothesis | `docs/REFERENCE_INVESTIGATION.md` |
| responses parsed at the boundary, not into fields | `docs/REFERENCE_INVESTIGATION.md` |
| alternative readings come from a fixed set | `src/hypothesis/alternatives.py` |
| the corpus is synthetic | `tests/corpus/` |

### Slide 19 — Закрытие

No numeric claim. Links: `REPORT.md`, `docs/REFERENCE_INVESTIGATION.md`,
`docs/demo.md`.
