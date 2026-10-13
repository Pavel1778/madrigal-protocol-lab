# Slide verification

Every numeric claim on the deck is checked against the code that produced it, so
a reviewer can move from a sentence on a slide to the evidence behind it. The
deck is `presentation/slides.md`; the rendered pages are `presentation/slides.pdf`
(fourteen pages). Where a slide quotes a number, the number is stated here with
the command that reproduces it. Everything below comes from `docs/METRICS.md`
and `docs/AUDIT.md`.

## Постановка

### Slide 3 — TCP разрезает сообщения посередине

No numeric claim. TCP delivers a byte stream; a message boundary is a property of
the protocol, not of the packet (`src/protocol/framing.py`).

### Slide 4 — Дано и требуется

No numeric claim. The inputs are the organizer captures (`tests/corpus/real/`)
and the device journal; the requirement is a verifiable reading of the message
structure.

## Метод

### Slide 5 — Три модуля связаны форматами, а не вызовами

No numeric claim. Four packages (`src/capture`, `src/protocol`, `src/hypothesis`,
`src/ui`) exchange JSON documents validated against JSON Schema draft 2020-12
(`docs/schemas/`); the call order does not matter. Approach and its basis:
`REPORT.md` sections 2 and 4.

### Slide 6 — От интерпретации можно вернуться к исходным данным

| claim | evidence |
| --- | --- |
| provenance carries packet index, sequence number and timestamp | `src/capture/` provenance records; shown live on `screenshots/09_provenance.png` |
| a missing packet becomes a gap, not zero bytes | `screenshots/04_hex_gap.png`; `docs/AUDIT.md` |

### Slide 7 — Правило проверяется на всём корпусе сразу

| claim | evidence |
| --- | --- |
| four framing families | `src/protocol/framing.py`: length-prefixed, fixed-size, delimiter, manual |
| field types include uint, enum, string, checksum, computed | `src/protocol/fields.py` |
| `hypothesis` marks a guess about meaning | field flag in `docs/schemas/rule.schema.json` |

### Slide 8 — Контрпример важнее метрики

| claim | evidence |
| --- | --- |
| six per-message statuses | `src/hypothesis/result.py`: matched, mismatched, incomplete, ambiguous, uncovered, not_applicable |
| counterexample byte: `s2` / `A_to_B`, offset 0, bytes `02 00 00 03 13 00 55` | `verify` output, `contradictions[0]` |
| 80 v1 mismatches sit on offset 0 in `s2` and `s3` | the same `verify` output: 60 `value 2 not in expected [1]`, 20 `value 3 not in expected [1]` |
| meaning outside the proposed set is never proposed | `src/hypothesis/alternatives.py` |

## Результаты

### Slide 9 — Что получилось: 60 из 140 → 140 из 140

| claim | evidence |
| --- | --- |
| v1: 60 matched, 80 mismatched | `python -m src.protocol.cli verify --rule examples/corpus_rule_v1.json --capture tests/corpus/reference_export/corpus_capture_01.normalized.json` |
| v2: 140 matched, 0 mismatched | `python -m src.protocol.cli verify` with the v2 rule |
| precision v1 0.43, v2 1.00 | `docs/METRICS.md`, `docs/RULE_V1_V2.md` |
| only the command set changes `[1]` → `[1, 2, 3]` | `git diff` between the two rule files; `docs/RULE_V1_V2.md` |
| an old result keeps its version and becomes `outdated` | `screenshots/08_diff.png` |

### Slide 10 — Осколки IP собираются в одно сообщение

| claim | evidence |
| --- | --- |
| IPv4 groups fragments by `id` and `protocol`, offset in units of eight bytes | `src/capture/fragment.py` |
| IPv6 groups by `id` and discards an overlapping datagram | `src/capture/fragment.py`; fixture `tests/fixtures/defects/fragment_overlap_ipv6.pcapng` |
| a hole is `incomplete`, not zero bytes | `src/capture/fragment.py`; fixture `tests/fixtures/defects/fragment_incomplete_missing.pcapng` |
| twelve fragmentation tests | `tests/capture/test_fragmentation.py` (12 collected) |

### Slide 11 — Набор организаторов разобран целиком

| claim | evidence |
| --- | --- |
| 90 messages: 45 requests + 45 responses, all matched | `docs/REAL_CORPUS_ANALYSIS.md`, `docs/METRICS.md` |
| the organizers' corpus was not used to refine the rule | `docs/REFERENCE_INVESTIGATION.md` |
| 12 s on 95.66 MiB, 250 000 packets, 1000 sessions | `docs/METRICS.md` |
| peak memory 350 MiB against a 4 GiB budget | `docs/METRICS.md` memory sweep |

### Slide 12 — Демонстрация: живое окно и запись прогона

No numeric claim. The window is `src/ui/`; the fallback recording is the demo
video referenced in `presentation/README.md`.

## Границы и итог

### Slide 13 — Границы и итог

| claim | evidence |
| --- | --- |
| flags byte constant, no reading separable | `docs/CORPUS_ANALYSIS.md` section 3 |
| value field unexplained, stays a hypothesis | `docs/REFERENCE_INVESTIGATION.md`; `REPORT.md` sections 10, 15 |
| the boundaries are demonstrated, not asserted | `REPORT.md` sections 5, 7, 8 |
| alternative readings come from a fixed set | `src/hypothesis/alternatives.py` |
| the corpus includes synthetic captures | `tests/corpus/` |

### Slide 14 — Закрытие

No numeric claim. Links: `REPORT.md`, `docs/REFERENCE_INVESTIGATION.md`,
`docs/demo.md`.
