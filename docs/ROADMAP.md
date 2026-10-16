# Roadmap

What is implemented, what was left out of the MVP, the technical debt, and
what a further month would add.

## Implemented

Requirements R1-R6 from the case, as closed by the code:

| Requirement | State | Where |
| --- | --- | --- |
| R1 source exchange: PCAP/PCAPNG, sessions, directions, reassembly, provenance, diagnostics | done | `src/capture/` |
| R2 research tools: search, comparison, hex view, action journal | done | `src/capture/`, `src/ui/` |
| R3 interpretations: declarative rules, versioning, reuse on new data | done | `src/protocol/`, `src/hypothesis/` |
| R4 verification: corpus, counterexamples, visible applicability, recheck | done | `src/hypothesis/` |
| R5 portable project: relative paths, manifest, versions, results | done | `src/project/` |
| R6 reuse: report (Markdown/HTML), machine-readable result (JSON), CLI | done | `src/report/`, `src/*/cli.py` |

## Out of MVP scope

The extensions the case names that were not built, with the reason and the
shape a first version would take.

| Extension | Why left out | First version |
| --- | --- | --- |
| Explainable pattern proposals: suggest field layouts the researcher did not state | Needs a search over offsets, widths and readings that is a project on its own; the current tool scores readings the researcher supplies | Enumerate candidate field boundaries over the framed bytes and rank by support/contradict, reusing the existing scoring |
| Automatic request/response linking | Needs the response rule, which was not derived; the corpus carries both directions but only the request direction is interpreted | Match by transaction id or by timestamp window, then check the field correspondence |
| Behaviour comparison between captures | The corpus is one protocol; a second protocol would be needed to make the comparison meaningful | Diff two projects by rule version and by message counts |
| Complex structures: nested, variable-length, repeated fields | The rule schema is flat fields; nesting would change the schema | A field kind `list` with a count field and a child layout |
| Controlled experiments: change one byte and observe | No live target; the captures are recorded | A project action that rewrites a message and re-runs the rule |

## Technical debt

| Item | Impact | Path |
| --- | --- | --- |
| encrypted payloads | out of scope by design | none; the tool reports the bytes it sees |
| memory scales with the capture | all packets held at once | session-by-session parse with provenance streamed to disk (see `docs/BENCHMARK.md`) |
| formatting and typing deferred | `ruff format --check` and `mypy` still report findings in modules outside the audited zone (the extended `ruff` set itself is enabled) | re-enable `ruff format --check .` and `mypy .` one zone at a time (see `docs/AUDIT.md`) |

## Product plan for a further month

1. Derive the response rule, then link requests to responses by transaction id;
   the corpus already holds both directions.
2. Pattern proposal: search field boundaries and rank readings, so a researcher
   starts from suggestions instead of a blank rule.
3. Second protocol in the corpus, so behaviour comparison has something to
   compare and the applicability boundary is exercised on real variance.
4. Memory-bounded mode by default: parse and reassemble session by session with
   provenance written as it is produced.
5. Fragment reassembly (IPv4 and IPv6) in the capture layer.
