# Slide verification

Every claim on the deck is checked against the code that produced it, so a
reviewer can move from a sentence on a slide to the evidence behind it. The deck
is `presentation/slides.md`; the rendered pages are `presentation/slides.pdf`.
Where a slide quotes a number, the number is stated here with the test or
command that reproduces it.

The heading numbers below are the printed page numbers of `slides.pdf`, so a
reviewer can jump straight to a page. The deck has fifteen pages; the interface
topic spans two of them (pages 7 and 8) and is verified once, under page 6.

## Slide 1 - Задача (the task)

No numeric claim. The problem is restated from the case: undocumented binary
protocol over TCP, a capture and a journal, no specification.

## Slide 2 - Подход (approach)

| claim | evidence |
| --- | --- |
| three independent modules joined by JSON formats | `docs/CONTRACT.md`, `docs/INTEGRATION.md`, `docs/schemas/` |
| formats fixed by JSON Schema draft 2020-12 | `docs/schemas/capture.schema.json`, `result.schema.json`, `rule.schema.json`; validated with `jsonschema.Draft202012Validator` in `tests/integration/test_reference_report.py`, `tests/protocol/test_rule.py` |
| formats do not change silently | `docs/CONTRACT.md` states the change rule; the schemas carry `contract_version` |

## Slide 3 - Захват потока (capture)

| claim | evidence |
| --- | --- |
| a session is a connection instance, not an address pair | `src/capture/` (capture module); session model in `src/protocol/stream.py` mirrors it; `tests/capture/` |
| retransmission adds provenance, not bytes | `provenance[]` ranges in the capture contract; `tests/capture/test_reassembly.py` |
| a gap is not zero-filled | `diagnostics[] {type: gap}`; `tests/protocol/test_engine.py::test_gap_in_field_range_is_incomplete` |
| each byte range remembers packet, seq and time | `provenance[]` entries in `docs/CONTRACT.md` |
| TCP packet boundaries are not message boundaries | `src/protocol/framing.py`; `tests/protocol/test_framing.py::test_length_prefixed_message_split_across_packet_boundary` |

The capture module is a separate concern (Agent 1's zone); this deck verifies
the protocol stage's use of its output, not the capture internals.

## Slide 4 - Правила и фрейминг (rules and framing)

| claim | evidence |
| --- | --- |
| a rule is declarative JSON | `src/protocol/rule.py`, schema in `docs/schemas/rule.schema.json` |
| framing by length, fixed size, markers, manual | `src/protocol/framing.py`; `tests/protocol/test_framing.py` |
| field types include ints, bytes, enums, strings, checksums, computed | `src/protocol/rule.py`; `docs/PROTOCOL_API.md` |
| `hypothesis: true` marks assumed meaning | `src/protocol/rule.py`; `src/hypothesis/alternatives.py` |
| one rule describes the whole stream | `src/protocol/engine.py::apply_rule`; `tests/integration/test_reference_report.py` |

## Slide 5 - Гипотезы и контрпримеры (hypotheses and counterexamples)

| claim | evidence |
| --- | --- |
| six statuses per message | `src/hypothesis/status.py`; `tests/hypothesis/test_status.py` |
| `mismatched` is a counterexample bound to bytes and packet | `Counterexample.to_dict()` carries `bytes_hex`, `session_id`, `message_offset`, `reason`; `tests/hypothesis/test_corpus.py` |
| a match on examples is not proof | `REPORT.md` section 3; `src/hypothesis/corpus.py` verifies over the whole corpus |
| counterexamples are kept, not discarded | `VerificationReport.contradictions`; `docs/REFERENCE_INVESTIGATION.md` |

## Slide 6 - Интерфейс (interface)

| claim | evidence |
| --- | --- |
| session tree left, bytes centre, results right, provenance below | `src/ui/main_window.py`, `src/ui/session_tree.py`, `src/ui/hex_view.py` |
| a session is marked when its stream has a gap or ambiguity | `src/ui/session_tree.py`; `tests/ui/test_main_window.py::test_defect_capture_surfaces_diagnostics` |
| a byte under a rule field is coloured by status | `src/ui/hex_view.py`; `tests/ui/test_main_window.py::test_hex_view_renders_the_stream` |

The eight screenshots were produced by `presentation/generate_screenshots.py`.

## Slide 9 - Демонстрация: цикл на корпусе (the cycle on the corpus)

The six steps are reproduced in `docs/demo.md` and, without the window, in
`docs/demo_cli.md`. The machine-checked form is
`tests/integration/test_reference_report.py`:

| step | evidence |
| --- | --- |
| observation: requests begin `01 00 00 01` | first bytes in `docs/REFERENCE_INVESTIGATION.md` |
| hypothesis: length at offset 2, two bytes big-endian | `examples/corpus_rule_v1.json` `framing` |
| corpus check: every stream framed without leftover | framing census in `docs/CORPUS_ANALYSIS.md` section 2 |
| counterexample: command `2` and `3` in the same sessions | `tests/integration/test_reference_report.py::test_refinement_resolves_every_v1_counterexample` |
| refinement: command set widens to `1, 2, 3` | diff of `examples/corpus_rule_v1.json` vs `corpus_rule_v2.json` |
| recheck: no counterexamples | `tests/integration/test_reference_report.py::test_v2_transfers_to_the_second_capture_without_counterexamples` |

## Slide 10 - Проверка и контрпримеры (verification)

| показатель | v1 | v2 | evidence |
| --- | --- | --- | --- |
| matched | 60 | 140 | `verify_on_corpus` over `corpus_capture_01`; `tests/integration/test_reference_report.py` |
| mismatched | 80 | 0 | same |
| точность (precision) | 0,43 | 1,00 | matched / (matched + mismatched): 60/140 and 140/140 |

A gap is not zero-filled: the message over it is `incomplete`
(`tests/hypothesis/test_corpus.py`, and `tests/protocol/test_engine.py`).

## Slide 11 - Сравнение и версии (comparison and versions)

| claim | evidence |
| --- | --- |
| the refinement changed only the allowed command list | `python -m src.protocol.cli diff --rule-a examples/corpus_rule_v1.json --rule-b examples/corpus_rule_v2.json --report-a ... --report-b ...`; output in `docs/RULE_V1_V2.md` section 4 |
| the old result stays on disk with its version and is marked outdated | `src/hypothesis/versioning.py::ResultStore.mark_outdated`; `tests/hypothesis/test_versioning.py` |

## Slide 12 - Воспроизводимость (reproducibility)

| claim | evidence |
| --- | --- |
| the whole reconstruction runs with one command and invents nothing | `scripts/run_reference_investigation.py`; the corpus smoke test is skipped, not faked, when the corpus is absent |
| a project is portable and reopens in another directory | `src/project/`; `docs/PORTABILITY.md`; `tests/integration/test_reference_report.py` move test |
| rules export to Kaitai Struct and to a standalone Python module | `src/protocol/export.py`; tests under `tests/protocol/test_export.py` |
| a command line applies, verifies and compares versions | `src/protocol/cli.py`; `tests/protocol/test_cli.py` |

## Slide 13 - Ограничения (limitations)

Every item is a real gap, stated rather than hidden:

| limitation | why it holds |
| --- | --- |
| the meaning of the flags byte is not established | it is constant across the corpus, so no reading can be distinguished; the rule declares `expected: [0]` |
| the value field is unexplained | no candidate reading survives on its own; it stays a hypothesis (`missing_ok: true`) |
| responses are parsed by length, not by fields | the rule scopes to `A_to_B`; `B_to_A` is `not_applicable` |
| alternative readings come from a fixed set | `src/hypothesis/alternatives.py` enumerates candidates; a meaning outside the set is not proposed |
| the corpus is synthetic | `tests/corpus/README.md`; the protocol may differ from a real device |

## Slide 14 - Итог (result)

| claim | evidence |
| --- | --- |
| the layout is command, flags, length, payload | `examples/corpus_rule_v2.json` fields |
| command takes `1, 2, 3`; offset 4 is a parameter id; offset 5-6 a written value | `REPORT.md`, `docs/REFERENCE_INVESTIGATION.md` |
| the rule transfers to the second capture and not to a foreign one | v2 on `corpus_capture_02` matches 40, on `synthetic_live` matches 0 with one `incomplete` |
| every claim is backed by bytes, a counterexample or the journal | `REPORT.md` sections 5, 9 and the counterexample table |

## Slide 15 - Вопросы (questions)

Points to `REPORT.md`, `docs/REFERENCE_INVESTIGATION.md` and `docs/demo.md`.

## How this file stays true

The figures here are the ones the deck quotes. If a figure on the deck changes,
this file and the reproducing command change with it. The corpus smoke test
(`tests/integration/test_reference_report.py`) fails if the report's framing
verdict, version comparison or boundary result drift from the captures, so the
numbers behind pages 9 to 11 cannot go stale unnoticed.

```
python -m pytest tests/integration/test_reference_report.py -q
python -m presentation.render_pdf    # slides.md -> slides.html -> slides.pdf
```
