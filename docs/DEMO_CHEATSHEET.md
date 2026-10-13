# Demo cheatsheet

One page to print and keep beside the keyboard. Two flows: the **organizer
dataset** (real bytes) and the **reference corpus** (where the 80
counterexamples live). Every command below was run on the committed tree; the
numbers are the ones the tool prints. Sources: `docs/REAL_CORPUS_ANALYSIS.md`,
`docs/METRICS.md`.

## Before the defense (do this once)

```bash
cd ~/madrigal-check && source .venv/bin/activate   # python 3.12+, pip install -e ".[dev,web]"
python -m src.capture.cli --pcap tests/corpus/real/research/01_configuration.pcap \
  --out /tmp/real-01.json
```

Ready: `/tmp/real-01.json`, **2 sessions**, 0 diagnostics. Real dataset, real
bytes.

Keep a second window with the reference export ready:

```bash
ls tests/corpus/reference_export/corpus_capture_01.normalized.json
```

---

## Flow A — the organizer dataset (real data)

### A1. GUI on the real data (30 s)

```bash
python -m src.ui.main_window \
  --capture /tmp/real-01.json \
  --rule examples/thermostand_request_v2.json
```

Say: «Открываем реальный набор организаторов. Две сессии, правило
`thermostand_request v2` даёт 14 запросов `matched` и 14 ответов
`not_applicable` — правило описывает только направление запросов. Клик по байту
— видно пакет-источник. Это provenance.»

(Verified: the rule report on this capture is `matched=14, mismatched=0,
not_applicable=14`. The full organizer set across all four captures is 45
requests + 45 responses, all matched.)

### A2. Full pipeline in one command (30 s)

```bash
python -m src.project.cli pipeline \
  --pcap tests/corpus/real/research/01_configuration.pcap \
  --rule examples/thermostand_request_v2.json \
  --project /tmp/demo --report /tmp/demo/REPORT.md
```

Say: «Одна команда — весь конвейер: захват → правило → проект → отчёт. Отчёт
самодостаточный HTML, открывается без сети. Это переносной проект.»

Output: `/tmp/demo/reports/REPORT.md` and `REPORT.html`, 2 sessions.

### A3. Web interface (optional, 20 s)

```bash
python -m src.web.app --capture /tmp/real-01.json \
  --rule examples/thermostand_request_v2.json --port 8765
```

Open <http://127.0.0.1:8765>. Say: «Веб — тонкая обёртка над тем же ядром.
Ядро отделено от интерфейсов JSON-контрактами.»

---

## Flow B — the reference corpus (the counterexample story)

### B1. GUI with the narrow rule v1 (30 s)

```bash
python -m src.ui.main_window \
  --capture tests/corpus/reference_export/corpus_capture_01.normalized.json \
  --rule examples/corpus_rule_v1.json
```

Say: «Правило v1 ожидает `command=1`. В корпусе 140 запросов; 60 совпали, 80 —
контрпримеры. Мы их не отбрасываем: каждый привязан к байтам.»

(Verified: v1 report is `matched=60, mismatched=80`.)

### B2. Refine to v2 (15 s)

In the GUI: **Файл → Открыть правило → `corpus_rule_v2.json`**, then apply to the
whole capture (F6).

Say: «Мы расширили только список команд `[1] → [1,2,3]`. Структура правила не
изменилась. 140 `matched`, 0 контрпримеров, точность 0.43 → 1.00.»

### B3. Version diff (15 s)

In the GUI: the **«Диф. версий»** tab, v1 vs v2.

Say: «Видно ровно одно изменение поля. Метрика выросла с 0.43 до 1.00.»

### B4. CLI clause of the same story (20 s, fallback)

```bash
python -m src.protocol.cli verify --rule examples/corpus_rule_v1.json \
  --capture tests/corpus/reference_export/corpus_capture_01.normalized.json
python -m src.protocol.cli verify --rule examples/corpus_rule_v2.json \
  --capture tests/corpus/reference_export/corpus_capture_01.normalized.json
```

Prints `280 messages, 80 counterexamples` then `280 messages, 0 counterexamples`.

---

## If something breaks

| Symptom | Fallback |
| --- | --- |
| GUI does not open | Show screenshots in `presentation/screenshots/` (e.g. `09_provenance.png`, `10_hypotheses.png`). |
| Qt import error (`libEGL`) | `sudo apt-get install -y libegl1 libgl1 libglib2.0-0 libxkbcommon0 libdbus-1-3 libfontconfig1`, retry; or use the CLI fallback B4. |
| Web does not start | Skip it; the window and the CLI carry the same point. |
| Real data unreadable | Use `tests/corpus/reference_export/` instead (the whole of Flow B). |
| Screen fails entirely | Play `presentation/screencast.mp4` (2:22, committed). |

## Know by heart

- **Three modules**: `capture` (bytes tied to packets), `protocol` + `hypothesis`
  (framing, rules, counterexamples), `ui` (the window).
- **Provenance** = every byte knows the packet it came from.
- **Counterexample** = the data where the rule fails; kept, not dropped.
- **Precision**: 0.43 → 1.00 (rule v1 → v2 on the reference corpus).
- **Real dataset**: 45 requests + 45 responses, all `matched`, 100 % byte coverage.
- **Framing**: 10/10 streams framed cleanly by `payload`; the other two
  candidates, 0/10.
- **Tests**: 840 with `[dev,web]` (815 with `[dev]` only); CI green.
- **Deck**: 14 slides; final slide has two QR codes, never the word «Вопросы».

Full answers: `docs/DEFENSE_FAQ.md`, `docs/FAQ_FOR_JUDGES.md`,
`presentation/Q_and_A.md`. Pre-flight list: `docs/DEFENSE_CHECKLIST.md`.
