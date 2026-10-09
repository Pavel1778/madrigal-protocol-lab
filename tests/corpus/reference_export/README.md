# Reference normalized exports

The normalized capture JSON for the three generated corpus records, produced by
the capture module. The protocol module and the GUI use these files for their
corpus smoke test and reference investigation, so they do not have to call the
capture module while their own work is in progress.

Because the captures are fixed, these files are byte for byte reproducible:
regenerating them from the same commit must not change a single byte.

## Contents

| File | Source capture | Sessions | Stream bytes |
| ---- | -------------- | -------- | ------------ |
| `corpus_capture_01.normalized.json` | `corpus_capture_01.pcapng` | 3 | 3036 |
| `corpus_capture_02.normalized.json` | `corpus_capture_02.pcapng` | 2 | 520 |
| `corpus_capture_defects.normalized.json` | `corpus_capture_defects.pcapng` | 1 | 74 |

`corpus_capture_defects` carries a `gap` in `A_to_B` and an `ambiguity` in
`B_to_A`; the other two carry no stream diagnostics.

Source digests (sha256), so a consumer can confirm the export matches the
capture it names:

| Capture | sha256 |
| ------- | ------ |
| `corpus_capture_01.pcapng` | `1a2f3637124abcd43049bdf9432ae3d18024276cf7de29efd43562e0c61f272c` |
| `corpus_capture_02.pcapng` | `4aa281b97de9afa09d74ff0f5c41e9f6c4fc2b7b07ddf314f33b55d2fec95afc` |
| `corpus_capture_defects.pcapng` | `ae93a5b22380874e743459ef68216249283eec4ee2bfcd96d01953319cdff0ce` |

The `capture_id` field inside each JSON is `sha256:` followed by the digest
above.

## How to regenerate

```
bash tests/corpus/reference_export/regenerate.sh
```

The script runs `python -m scripts.generate_reference_export`, which rebuilds
each file from `tests/corpus` and validates it against
`docs/schemas/capture.schema.json` before writing. If a record ever grows past
1 MiB the file is written gzip compressed as `*.normalized.json.gz`; the script
then unpacks it so `*.normalized.json` is always present.

## How validity is confirmed

- Every document is checked with `jsonschema` (draft 2020-12) against
  `docs/schemas/capture.schema.json` at generation time; a failure stops the
  build and no file is written.
- `tests/integration/test_corpus_capture.py` rebuilds the same exports from the
  corpus and checks schema validity, the byte round trip, and provenance, so a
  regression fails CI rather than silently drifting these files.

## Version used

- Capture module API contract version: 1 (`contract_version` in each file).
- Project version: 0.1.0 (`pyproject.toml`).
- Generated at commit `9e2cd07` on branch `agent1/capture`.
