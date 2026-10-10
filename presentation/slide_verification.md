# Slide verification

Every numeric claim on the deck is checked against the code that produced it, so
a reviewer can move from a sentence on a slide to the evidence behind it. The
deck is `presentation/slides.md`; the rendered pages are `presentation/slides.pdf`
(eighteen pages). Where a slide quotes a number, the number is stated here with
the command that reproduces it. Everything below comes from `docs/METRICS.md`
and `docs/AUDIT.md`.

## Подход

### Slide 4 — Архитектура

No numeric claim. Three modules (`src/capture`, `src/protocol` and
`src/hypothesis`, `src/ui`) exchanged through JSON documents validated against
JSON Schema draft 2020-12 (`docs/schemas/`).

## Реализация

### Slide 6 — Захват потока

| claim | evidence |
| --- | --- |
| provenance carries packet index, sequence number and timestamp | `src/capture/` provenance records; shown live on `screenshots/09_provenance.png` |
| a missing packet becomes a gap, not zero bytes | `screenshots/04_hex_gap.png`; `docs/AUDIT.md` |

### Slide 7 — Правила и фрейминг

| claim | evidence |
| --- | --- |
| four framing families | `src/protocol/framing.py`: length-prefixed, fixed-size, delimiter, manual |
| six field types | `src/protocol/fields.py`: uint, bytes, enum, string, checksum, computed |
| `hypothesis` marks a guess about meaning | field flag in `docs/schemas/rule.schema.json` |

### Slide 8 — Гипотезы и контрпримеры

| claim | evidence |
| --- | --- |
| six per-message statuses | `src/hypothesis/result.py`: matched, mismatched, incomplete, ambiguous, uncovered, not_applicable |
| a rule is checked against the whole corpus | `python -m src.protocol.cli verify`; `docs/METRICS.md` |

## Демонстрация

### Slide 10 — Цикл на корпусе

| claim | evidence |
| --- | --- |
| the six-step cycle | `docs/REFERENCE_INVESTIGATION.md`, `docs/demo.md` |
| request bytes begin `01 00 00 01` | `docs/CORPUS_ANALYSIS.md` |

### Slide 11 — Проверка и контрпримеры

| claim | evidence |
| --- | --- |
| v1: 60 matched, 80 mismatched | `python -m src.protocol.cli verify --rule examples/corpus_rule_v1.json --capture tests/corpus/reference_export/corpus_capture_01.normalized.json` |
| the 80 counterexamples are 60 bytes of `2` and 20 bytes of `3` | the same `verify` output: 60 `value 2 not in expected [1]` in `s2`, 20 `value 3 not in expected [1]` in `s3` |
| precision v1 0.43, v2 1.00 | `docs/METRICS.md`, `docs/RULE_V1_V2.md` |

### Slide 12 — Сравнение версий

| claim | evidence |
| --- | --- |
| only the command set changes `[1]` → `[1, 2, 3]` | `git diff` between the two rule files; `docs/RULE_V1_V2.md` |
| an old result keeps its version and becomes `outdated` | `screenshots/08_diff.png` |

### Slide 13 — Контрпример как ценность

| claim | evidence |
| --- | --- |
| counterexample byte: `s2` / `A_to_B`, offset 0, bytes `02 00 00 03 13 00 55` | `verify` output, `contradictions[0]` |
| packet 128, seq 20001 | provenance range in the same output |
| meaning outside the proposed set is never proposed | `src/hypothesis/alternatives.py` |

## Итог

### Slide 14 — Метрики

| claim | evidence |
| --- | --- |
| v2: 140 matched, 0 mismatched | `python -m src.protocol.cli verify` with the v2 rule |
| 10/10 streams, 280 messages | `docs/METRICS.md`, `docs/CORPUS_ANALYSIS.md` |
| transfer: 40/40 on the second capture | `docs/METRICS.md` |
| CI green, 5/5 checks | `docs/AUDIT.md` |
| streaming below regular at 10/50/95 MiB | `docs/METRICS.md` memory sweep |

### Slide 16 — Ограничения

| claim | evidence |
| --- | --- |
| flags byte constant (`0x00`), no reading separable | `docs/CORPUS_ANALYSIS.md` section 3 |
| value field unexplained, stays a hypothesis | `docs/REFERENCE_INVESTIGATION.md` |
| responses parsed at the boundary, not into fields | `docs/REFERENCE_INVESTIGATION.md` |
| alternative readings come from a fixed set | `src/hypothesis/alternatives.py` |
| the corpus is synthetic | `tests/corpus/` |

### Slide 17 — Итог и ссылки

| claim | evidence |
| --- | --- |
| layout: command code, flags, length (uint16, BE), payload | `examples/corpus_rule_v1.json`, `examples/corpus_rule_v2.json` |
| rule transfers to the second capture and not to a foreign one | `docs/METRICS.md` |

## Slide 18 — Вопросы

No numeric claim. Links: `REPORT.md`, `docs/REFERENCE_INVESTIGATION.md`,
`docs/demo.md`.
