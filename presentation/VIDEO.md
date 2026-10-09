# Video scenario

A three to five minute screen recording of the reference investigation. The
recording can be made on any machine with a display; the tool is not tied to a
particular platform.

## Tool

- OBS Studio with a display capture source, or
- ffmpeg with the X11 grabber:

```
ffmpeg -f x11grab -framerate 25 -video_size 1440x880 -i :0.0+0,0 \
  -c:v libx264 -pix_fmt yuv420p presentation/video.mp4
```

Before recording, set the window to 1440 by 880 and hide the terminal.

## Shot list

| time | shot | action | narration |
| --- | --- | --- | --- |
| 0:00 | title | show the window title bar | The tool reconstructs an undocumented binary protocol from captures. |
| 0:15 | sessions | open `corpus_capture_01.normalized.json` | Three sessions, two directions each, and the diagnostics of the capture. |
| 0:40 | provenance | hover the first bytes of `s1 A_to_B` | Each byte remembers its packet, sequence number and time. |
| 1:05 | framing | switch to the Rule tab, show the framing block | One description frames the whole stream; packet boundaries are not message boundaries. |
| 1:30 | apply v1 | press F5 | The first rule matches reads and fails on the other commands; the failures are counterexamples. |
| 2:00 | counterexample | open the Counterexamples tab, select the first entry | Command `2` was not allowed; the bytes are highlighted and tied to a packet. |
| 2:30 | refine | open `corpus_rule_v2.json`, press F5 | The allowed commands widen to `1`, `2`, `3`; the counterexamples disappear. |
| 3:00 | whole capture | press F6 | Over the whole capture: 140 matched, 0 counterexamples. The earlier run is marked outdated. |
| 3:30 | boundary | open the synthetic capture, press F6 | A different layout: nothing matches. The rule does not transfer, and the tool says so. |
| 4:00 | report | Report, Show REPORT.md | The investigation, its counterexamples and its limits are written up. |

## Notes

- Keep the pointer still while the narration runs.
- Do not cut the boundary shot: it is the part that shows the limits are real.
- If the window is unavailable, record the command line from `docs/demo.md`
  instead; the steps and the narration are the same.
