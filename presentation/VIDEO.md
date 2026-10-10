# Reserve video

A three to five minute screen recording of the reference investigation, kept as
a fallback for the defense in case the live demonstration fails. The recording
runs on any machine with a display; the tool is not tied to a platform.

Target length: 4 minutes. Six scenes. Every number spoken is from
`docs/METRICS.md`; the window path is the one in `docs/demo.md`.

## Tool

- OBS Studio with a display capture source, or
- ffmpeg with the X11 grabber:

```
ffmpeg -f x11grab -framerate 25 -video_size 1440x880 -i :0.0+0,0 \
  -c:v libx264 -pix_fmt yuv420p presentation/video.mp4
```

An offline driver, `record_demo.py`, performs the six scenes with the real
window code and a caption band, so the take is reproducible without a speaker.
It is a recording aid only: the window is unchanged and each action is the one a
menu performs. Record the screen while it runs, then crop to the window frame it
prints at start-up:

```
python presentation/record_demo.py     # under a display, prints its geometry
```

Before recording, set the window to 1440 by 880, hide the terminal, and mute
notifications. Keep the pointer still while the narration runs.

## Recording script (run once before pressing record)

```
python -m scripts.generate_corpus
python -m src.capture.cli --pcap tests/corpus/corpus_capture_01.pcapng \
  --out tests/corpus/reference_export/corpus_capture_01.normalized.json \
  --source-name captures/corpus_capture_01.pcapng
python -m src.ui.main_window \
  --capture tests/corpus/reference_export/corpus_capture_01.normalized.json \
  --rule examples/corpus_rule_v1.json
```

Then, in the window, do exactly the six scenes below. Each scene starts from the
state the previous one left, so the recording is one continuous take.

## Storyboard

### Scene 1 — Title and sessions (0:00–0:40)

| | |
| --- | --- |
| Screen | the main window with the capture already loaded |
| Action | pause on the session tree; expand `s1`, `s2`, `s3` |
| Say | The tool reconstructs an undocumented binary protocol from captures. This capture has three sessions, two directions each. Each byte here belongs to a packet; nothing is invented. |

### Scene 2 — Bytes and provenance (0:40–1:25)

| | |
| --- | --- |
| Screen | the hex view, centre panel |
| Action | select session `s2`, direction `A_to_B`; hover the first bytes and click one |
| Say | The bytes are ordered by sequence number, not by arrival. A click shows the source packet, its sequence number and its time. A retransmission adds provenance, not bytes; a gap is a marker, not zeros. |

### Scene 3 — Rule and first apply (1:25–2:15)

| | |
| --- | --- |
| Screen | the Rule and Interpretation tabs |
| Action | open `examples/corpus_rule_v1.json` (Ctrl+R); press F5 |
| Say | A rule is a declarative description: where a message ends and what its fields mean. Packet boundaries are not message boundaries. Applying it to the whole capture, some messages match and some do not; the mismatches are kept as counterexamples. |

### Scene 4 — Counterexample and refinement (2:15–3:05)

| | |
| --- | --- |
| Screen | the Counterexamples panel; then the Rule tab with v2 |
| Action | select the first counterexample; click it to jump to its bytes; open `examples/corpus_rule_v2.json`; press F5 |
| Say | This byte carries command 2, which rule v1 did not allow; it is tied to a packet. Widening the allowed commands from 1 to 1, 2, 3 removes all 80 counterexamples: matched rises from 60 to 140, precision from 0.43 to 1.00. The old result keeps its version and is marked outdated. |

### Scene 5 — Transfer and boundary (3:05–3:45)

| | |
| --- | --- |
| Screen | the whole capture (F6); then the second capture |
| Action | open `corpus_capture_02.normalized.json`, press F6; then open the synthetic capture's normalized export and press F6 |
| Say | The same rule transfers to the second capture: 40 requests, 0 counterexamples. On a foreign capture with a different layout it matches nothing, and the tool says so instead of guessing. That is the measured boundary. |

### Scene 6 — Report and close (3:45–4:15)

| | |
| --- | --- |
| Screen | the Report tab |
| Action | Show REPORT.md, then scroll to the limitations section |
| Say | The investigation, its counterexamples and its limits are written up with the bytes attached. The interpretation is confirmed inside the tested scope and silent outside it. The repository and the report are on the last slide. |

## Notes

- Do not cut scene 5: the boundary is the part that shows the limits are real.
- If the window is unavailable, record the command line from `docs/demo_cli.md`
  instead; the narration is unchanged.
- Write the finished file to `presentation/video.mp4` (large binary, not
  committed; the shot list and the script are the committed artifacts).

## Measured result

`presentation/video.mp4` is the recorded take: 1680 by 1050, H.264, 3:39
(219.4 s), about 3.5 MB. The window capture sat inside a display whose top-left
corner was not the window origin, so the raw take carried solid black bands at
both ends; it was trimmed to the first and last frame with content
(`-ss 5 -to 224.4` on the raw take) and re-encoded, keeping the frame size and
scale. The duration is asserted with blackdetect on the first and last two
seconds.

The six scenes fit the first 3:45; the last thirty seconds are the close. The
finished file is not committed, and is distinct from
`presentation/screencast.mp4`, the shorter 1:25 clip embedded on the team slide;
the two are separate takes.
