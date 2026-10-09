# Reference investigation

## Observations

- Corpus: corpus_capture_01.pcapng (capture_id sha256:1a2f3637124abcd43049bdf9432ae3d18024276cf7de29efd43562e0c61f272c).
- Rule v1 scope: A_to_B.
- Messages framed: 280.
- Counts: matched=60, mismatched=80, incomplete=0, ambiguous=0, uncovered=0, not_applicable=140, outdated=0, unknown=0
- First bytes of the primary capture, as the observation the layout was read from:

```
s1 A_to_B: 010000011001000001110100000112010000011001000001
```

## Framing

The length field is at offset 2, two bytes, big-endian. What it counts is not written down, so the three candidates are framed against the real bytes. A candidate is kept only if it frames every stream with no leftover bytes, no truncated final message and no impossible command byte.

| capture | stream | bytes | payload | payload_and_length_field | entire_message |
| --- | --- | --- | --- | --- | --- |
| corpus_capture_01.pcapng | s1 A_to_B | 300 | 60 msgs, 300/300 B, clean | 1 msgs, 0/300 B, broken | 1 msgs, 0/300 B, broken |
| corpus_capture_01.pcapng | s1 B_to_A | 420 | 60 msgs, 420/420 B, clean | 3 msgs, 420/420 B, broken | 1 msgs, 0/420 B, broken |
| corpus_capture_01.pcapng | s2 A_to_B | 420 | 60 msgs, 420/420 B, clean | 2 msgs, 420/420 B, broken | 1 msgs, 0/420 B, broken |
| corpus_capture_01.pcapng | s2 B_to_A | 420 | 60 msgs, 420/420 B, clean | 2 msgs, 420/420 B, broken | 1 msgs, 0/420 B, broken |
| corpus_capture_01.pcapng | s3 A_to_B | 100 | 20 msgs, 100/100 B, clean | 1 msgs, 0/100 B, broken | 1 msgs, 0/100 B, broken |
| corpus_capture_01.pcapng | s3 B_to_A | 1376 | 20 msgs, 1376/1376 B, clean | 3 msgs, 1376/1376 B, broken | 2 msgs, 1376/1376 B, broken |
| corpus_capture_02.pcapng | s1 A_to_B | 100 | 20 msgs, 100/100 B, clean | 1 msgs, 0/100 B, broken | 1 msgs, 0/100 B, broken |
| corpus_capture_02.pcapng | s1 B_to_A | 140 | 20 msgs, 140/140 B, clean | 2 msgs, 140/140 B, broken | 1 msgs, 0/140 B, broken |
| corpus_capture_02.pcapng | s2 A_to_B | 140 | 20 msgs, 140/140 B, clean | 2 msgs, 140/140 B, broken | 1 msgs, 0/140 B, broken |
| corpus_capture_02.pcapng | s2 B_to_A | 140 | 20 msgs, 140/140 B, clean | 2 msgs, 140/140 B, broken | 1 msgs, 0/140 B, broken |

Only `payload` frames all 10 streams with no leftover bytes and no truncated message. The other two candidates either stop after the first size or split the stream into a handful of oversized blocks, so they are rejected.

## Counterexamples

80 counterexamples against rule v1:

- status=mismatched session=s2 direction=A_to_B message_offset=0 field=command reason=value 2 not in expected [1]
  bytes_hex=02000003130055
- status=mismatched session=s2 direction=A_to_B message_offset=7 field=command reason=value 2 not in expected [1]
  bytes_hex=020000031400ff
- status=mismatched session=s2 direction=A_to_B message_offset=14 field=command reason=value 2 not in expected [1]
  bytes_hex=0200000315009f
- status=mismatched session=s2 direction=A_to_B message_offset=21 field=command reason=value 2 not in expected [1]
  bytes_hex=0200000313005c
- status=mismatched session=s2 direction=A_to_B message_offset=28 field=command reason=value 2 not in expected [1]
  bytes_hex=02000003140003
- status=mismatched session=s2 direction=A_to_B message_offset=35 field=command reason=value 2 not in expected [1]
  bytes_hex=0200000315002b
- status=mismatched session=s2 direction=A_to_B message_offset=42 field=command reason=value 2 not in expected [1]
  bytes_hex=02000003130021
- status=mismatched session=s2 direction=A_to_B message_offset=49 field=command reason=value 2 not in expected [1]
  bytes_hex=02000003140010
- status=mismatched session=s2 direction=A_to_B message_offset=56 field=command reason=value 2 not in expected [1]
  bytes_hex=020000031500b1
- status=mismatched session=s2 direction=A_to_B message_offset=63 field=command reason=value 2 not in expected [1]
  bytes_hex=020000031300e2
- status=mismatched session=s2 direction=A_to_B message_offset=70 field=command reason=value 2 not in expected [1]
  bytes_hex=0200000314003c
- status=mismatched session=s2 direction=A_to_B message_offset=77 field=command reason=value 2 not in expected [1]
  bytes_hex=020000031500eb
- ... and 68 more of the same kind (each one is a command byte outside the expected set).

## Refinement

Rule refined to v2. Changes:

- field command: expected [1] -> [1, 2, 3]

Counts after refinement: matched=140, mismatched=0, incomplete=0, ambiguous=0, uncovered=0, not_applicable=140, outdated=0, unknown=0
Resolved counterexamples: 80.
Introduced counterexamples: 0.

## Applicability

Rule v2 applied to corpus_capture_02.pcapng (capture_id sha256:4aa281b97de9afa09d74ff0f5c41e9f6c4fc2b7b07ddf314f33b55d2fec95afc).
Counts: matched=40, mismatched=0, incomplete=0, ambiguous=0, uncovered=0, not_applicable=40, outdated=0, unknown=0.
Counterexamples: 0.

## Journal correlation

Journal: 185 entries; the timestamp is the capture time of the request packet. Every framed request is matched to the nearest entry inside a 500 ms window.

| capture | direction | requests | correlated | unmatched requests | unmatched entries | target=parameter | value=result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| corpus_capture_01.pcapng | A_to_B | 140 | 140 | 0 | 45 | 140 | 0/0 |
| corpus_capture_02.pcapng | A_to_B | 40 | 40 | 0 | 145 | 40 | 0/0 |

Every request lands on a journal entry at the same timestamp, and the `target` field resolves to the parameter the journal names for every correlated request. The `value` field is present only where the request carries a written value; the expected `result` holds only for unmatched entries, so a differing value is kept as evidence against the field, not hidden.

## Alternative readings

Fields marked `hypothesis: true` are named on a guess. Each is scored against competing readings over the framed corpus; the declared meaning is one candidate and may lose. Score is support / (support + contradict).

Field `command` (140 values):

| reading | support | contradict | score |
| --- | --- | --- | --- |
| low_cardinality | 140 | 0 | 1.00 |
| counter | 137 | 2 | 0.99 |
| constant | 60 | 80 | 0.43 |
| message_length | 0 | 140 | 0.00 |
| remaining_length | 0 | 140 | 0.00 |

Best fit: `low_cardinality`.

Field `target` (140 values):

| reading | support | contradict | score |
| --- | --- | --- | --- |
| low_cardinality | 140 | 0 | 1.00 |
| constant | 20 | 120 | 0.14 |

Best fit: `low_cardinality`.

Field `value` (60 values):

| reading | support | contradict | score |
| --- | --- | --- | --- |
| constant | 1 | 59 | 0.02 |
| message_length | 1 | 59 | 0.02 |
| remaining_length | 0 | 60 | 0.00 |

Best fit: `constant`.

## Open questions

- Field meanings marked `hypothesis: true` remain assumptions; a rule that matches is not proof.
- Behaviour outside the tested captures is unknown; the rule is only confirmed within the tested domain.
