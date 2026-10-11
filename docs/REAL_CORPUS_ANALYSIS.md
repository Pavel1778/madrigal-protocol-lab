# Real corpus analysis: the organizer dataset

The organizer supplied a capture set for the thermal-stand protocol. It is
committed under `tests/corpus/real/` and analysed with the same pipeline the
application uses, so these numbers describe the shipped files and the shipped
code. The generated report is `docs/DATASET_INVESTIGATION.md`; the reproduction
command is `python -m scripts.investigate_dataset`.

## 1. What the dataset contains

| File | Role |
| --- | --- |
| `research/01_configuration.pcap` | configuration changes and measurements, two TCP sessions |
| `research/02_variations.pcapng` | other settings, negative temperatures, labels of several lengths, Cyrillic, rejected requests |
| `research/03_combined_messages.pcap` | several actions in one client send, different packet splits |
| `additional/04_new_observations.pcapng` | a second experiment with other values and batch sizes |
| `diagnostics/01..08` | variants of the third record, each with one capture or integrity condition |
| `action_journal.csv` | 109 actions with parameters, time and the result the client showed |
| `dataset_manifest.json` | the set composition and data origin |

The organizer's own `README_RU.md` states the origin: the application bytes come
from a real client/simulator TCP socket exchange on localhost, while the
Ethernet/IP/TCP framing, segmentation and clock are generated. The set is a
protocol-function check, not a passive capture of a device.

`dataset_manifest.json` records the expected session and action counts per
research capture. The pipeline reproduces the session counts exactly.

## 2. Sessions and streams

| Capture | Sessions | Stream bytes | Journal actions |
| --- | --- | --- | --- |
| `research/01_configuration.pcap` | 2 | 443 | 14 |
| `research/02_variations.pcapng` | 1 | 608 | 15 |
| `research/03_combined_messages.pcap` | 1 | 358 | 8 |
| `additional/04_new_observations.pcapng` | 1 | 384 | 8 |
| total | 5 | 1793 | 45 |

The session counts match `dataset_manifest.json` (2, 1, 1, 1).

## 3. Message framing and rules

Two rules describe the protocol: `examples/thermostand_request_v2.json`
(direction `A_to_B`) and `examples/thermostand_response_v2.json`
(direction `B_to_A`). Both use a length-prefixed frame whose two-byte length
field counts the four-byte header, carried as `length_bias: 4`.

| Direction | Messages | matched | mismatched | incomplete | ambiguous | uncovered |
| --- | --- | --- | --- | --- | --- | --- |
| requests | 45 | 45 | 0 | 0 | 0 | 0 |
| responses | 45 | 45 | 0 | 0 | 0 | 0 |

Every message in the research captures is framed and matched, covering 100 % of
the bytes in both directions. The `not_applicable` count in a rule report is the
other-direction traffic, which is expected.

### Per capture

| Capture | Request messages | Response messages |
| --- | --- | --- |
| `01_configuration` | 14 | 14 |
| `02_variations` | 15 | 15 |
| `03_combined_messages` | 8 | 8 |
| `04_new_observations` | 8 | 8 |

## 4. Fields identified

| Field | Type | Offset (request / response) | Note |
| --- | --- | --- | --- |
| `magic` | uint16 | 0 / 0 | constant `0xa65c` (42588) |
| `body_length` | uint16 | 2 / 2 | counts the four-byte header |
| `message_counter` | uint16 | 4 / 4 | increments per exchange |
| `message_type` | enum | 6 / 6 | request 16/32/48/126, response 272/288/304/382 |
| `status` | enum | — / 8 | 0 ok, 1..4 error codes |
| `enabled` | uint8 | 8 / 9 | hypothesis, set-config and config replies |
| `period_ms` | uint16 | 9 / 10 | hypothesis |
| `threshold_raw` | int16 | 11 / 12 | hypothesis |
| `label` | string | 14 / 15 | hypothesis, length in a preceding uint8 |
| `requested_count` | uint8 | 8 / — | read-values request |
| `measurement_count` | uint8 | — / 9 | number of measurement records |
| `device_time_ms` | array uint32 | — / 10 | hypothesis, stride 7 |
| `temperature_raw` | array int16 | — / 14 | hypothesis, stride 7; scale 0.01 °C |
| `alarm` | array uint8 | — / 16 | hypothesis, stride 7 |

The enum values were cross-checked against the journal: each decoded
`message_type` corresponds to the action the journal records at the same time.

## 5. Counterexamples and refinement

The first reading, `examples/thermostand_request_v1.json`, assumes the length
field counts the payload only. On the configuration capture it produces six
counterexamples: the first message is framed four bytes short, so `magic` reads
at the wrong offset and `message_counter` falls outside the message.

| Rule | matched | mismatched | incomplete |
| --- | --- | --- | --- |
| v1 (payload-only length) | 0 | 5 | 10 |
| v2 (length includes the header) | 45 | 0 | 0 |

The fix is the four-byte header bias (`length_bias: 4`), which v2 carries. The
counterexamples are the evidence; they are kept in the investigation, not
dropped.

## 6. Diagnostics

Each diagnostic capture is built to exercise one condition. The table is what
the reassembler actually reports.

| Capture | Condition | Reported |
| --- | --- | --- |
| `01_retransmission` | same-bytes retransmission | deduplicated (one retransmission recorded in `B_to_A`, no duplicate bytes) |
| `02_reordered` | reordered packets | reassembled in sequence order, no gap |
| `03_missing_segment` | missing segment | `gap` |
| `04_snaplen_truncated` | truncated snapshot | `gap` |
| `05_conflicting_overlap` | conflicting overlap | `ambiguity` |
| `06_missing_beginning` | no connection start | `syn_seen=False`, sequence roles UNKNOWN, stream still built |
| `07_checksum_offload` | partial pseudo-header checksum | `checksum_offload` when verification is on |
| `08_bad_checksum` | invalid checksum | `checksum_offload` when verification is on |

Checksum verification is off by default because of offloading; the last two rows
appear only with `ignore_checksums=False`.

## 7. Journal correlation

The action journal holds 109 entries. Applying the request rule to the
configuration capture and correlating with the journal gives:

```
14 of 14 messages correlated, 95 journal entries unmatched
```

Every decoded request message maps to the operator action it performs, and the
decoded parameters agree with the recorded values. The unmatched entries belong
to the other captures, which were not part of that correlation run.

## 8. Comparison with the synthetic corpus

| Property | Synthetic corpus | Organizer dataset |
| --- | --- | --- |
| Origin | generated end to end | application bytes from a real socket, framing generated |
| Protocol | `0x01`-led length-prefixed frame | `0xa65c` magic, header-counting length |
| Research captures | 1 primary + 1 held out | 3 research + 1 additional |
| Defect captures | 1 combined | 8, one condition each |
| Messages | 280 framed | 90 (45 + 45) |
| Rule outcome | v1 gives 80 counterexamples, v2 clears them | v1 gives 6 counterexamples, v2 clears them |

Both corpora exercise the same refinement loop: a naive rule, counterexamples
tied to bytes, a versioned fix, and a clean verification afterwards. The
organizer set adds finer defect coverage (eight single-condition captures) and a
second, independent protocol with a different framing convention.

## 9. Applicability and limits

- The rules are confirmed over 90 messages in four captures, not proven. The
  organizer states the framing headers are generated, so header-level
  behaviour seen here should be re-checked against a passive capture.
- `temperature_raw` is a hypothesis with a scale of 0.01 °C; the positiveness of
  the scale rests on the journal values, not on a byte-level invariant.
- The measurement arrays use a fixed seven-byte stride; a record of a different
  length would be reported `incomplete`, not silently mis-read.
- Error replies carry a one-byte body, so the configuration fields after
  `status` are correctly out of the message.

## 10. How to reproduce

```
python -m scripts.investigate_dataset          # writes docs/DATASET_INVESTIGATION.md
pytest tests/hypothesis/test_real_corpus.py -v # the end-to-end checks
```
