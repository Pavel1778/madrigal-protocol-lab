# Шпаргалка демонстрации

Английский оригинал: [DEMO_CHEATSHEET.md](../DEMO_CHEATSHEET.md).

Одна страница для печати и хранения рядом с клавиатурой. Два потока: **набор
организатора** (реальные байты) и **эталонный корпус** (где живут 80 контрпримеров).
Каждая команда ниже выполнена на закоммиченном дереве; числа — те, что печатает
инструмент. Источники: `docs/REAL_CORPUS_ANALYSIS.md`, `docs/METRICS.md`.

## Перед защитой (сделать один раз)

```bash
cd ~/madrigal-check && source .venv/bin/activate   # python 3.12+, pip install -e ".[dev,web]"
python -m src.capture.cli --pcap tests/corpus/real/research/01_configuration.pcap \
  --out /tmp/real-01.json
```

Готово: `/tmp/real-01.json`, **2 сессии**, 0 диагностик. Реальный набор, реальные
байты.

Держите второе окно с готовой эталонной выгрузкой:

```bash
ls tests/corpus/reference_export/corpus_capture_01.normalized.json
```

---

## Поток A — набор организатора (реальные данные)

### A1. GUI на реальных данных (30 с)

```bash
python -m src.ui.main_window \
  --capture /tmp/real-01.json \
  --rule examples/thermostand_request_v2.json
```

Говорим: «Открываем реальный набор организаторов. Две сессии, правило
`thermostand_request v2` даёт 14 запросов `matched` и 14 ответов
`not_applicable` — правило описывает только направление запросов. Клик по байту
— видно пакет-источник. Это provenance.»

(Проверено: отчёт правила на этом захвате — `matched=14, mismatched=0,
not_applicable=14`. Полный набор организатора по всем четырём захватам — 45
запросов + 45 ответов, все matched.)

### A2. Полный конвейер одной командой (30 с)

```bash
python -m src.project.cli pipeline \
  --pcap tests/corpus/real/research/01_configuration.pcap \
  --rule examples/thermostand_request_v2.json \
  --project /tmp/demo --report /tmp/demo/REPORT.md
```

Говорим: «Одна команда — весь конвейер: захват → правило → проект → отчёт. Отчёт
самодостаточный HTML, открывается без сети. Это переносной проект.»

Выход: `/tmp/demo/reports/REPORT.md` и `REPORT.html`, 2 сессии.

### A3. Веб-интерфейс (необязательно, 20 с)

```bash
python -m src.web.app --capture /tmp/real-01.json \
  --rule examples/thermostand_request_v2.json --port 8765
```

Откройте <http://127.0.0.1:8765>. Говорим: «Веб — тонкая обёртка над тем же ядром.
Ядро отделено от интерфейсов JSON-контрактами.»

---

## Поток B — эталонный корпус (история контрпримера)

### B1. GUI с узким правилом v1 (30 с)

```bash
python -m src.ui.main_window \
  --capture tests/corpus/reference_export/corpus_capture_01.normalized.json \
  --rule examples/corpus_rule_v1.json
```

Говорим: «Правило v1 ожидает `command=1`. В корпусе 140 запросов; 60 совпали, 80 —
контрпримеры. Мы их не отбрасываем: каждый привязан к байтам.»

(Проверено: отчёт v1 — `matched=60, mismatched=80`.)

### B2. Уточнить до v2 (15 с)

В GUI: **Файл → Открыть правило → `corpus_rule_v2.json`**, затем применить ко всему
захвату (F6).

Говорим: «Мы расширили только список команд `[1] → [1,2,3]`. Структура правила не
изменилась. 140 `matched`, 0 контрпримеров, точность 0.43 → 1.00.»

### B3. Diff версий (15 с)

В GUI: вкладка **«Диф. версий»**, v1 против v2.

Говорим: «Видно ровно одно изменение поля. Метрика выросла с 0.43 до 1.00.»

### B4. CLI-вариант той же истории (20 с, резерв)

```bash
python -m src.protocol.cli verify --rule examples/corpus_rule_v1.json \
  --capture tests/corpus/reference_export/corpus_capture_01.normalized.json
python -m src.protocol.cli verify --rule examples/corpus_rule_v2.json \
  --capture tests/corpus/reference_export/corpus_capture_01.normalized.json
```

Печатает `280 messages, 80 counterexamples`, затем
`280 messages, 0 counterexamples`.

---

## Если что-то сломалось

| Симптом | Резерв |
| --- | --- |
| GUI не открывается | Покажите снимки в `presentation/screenshots/` (например `09_provenance.png`, `10_hypotheses.png`). |
| Ошибка импорта Qt (`libEGL`) | `sudo apt-get install -y libegl1 libgl1 libglib2.0-0 libxkbcommon0 libdbus-1-3 libfontconfig1`, повторите; или используйте резерв CLI B4. |
| Веб не запускается | Пропустите; окно и CLI несут ту же мысль. |
| Реальные данные нечитаемы | Используйте `tests/corpus/reference_export/` вместо них (весь поток B). |
| Экран отказал полностью | Проиграйте `presentation/screencast.mp4` (2:22, закоммичен). |

## Знать наизусть

- **Три модуля**: `capture` (байты привязаны к пакетам), `protocol` + `hypothesis`
  (фрейминг, правила, контрпримеры), `ui` (окно).
- **Провенанс** = каждый байт знает пакет, из которого пришёл.
- **Контрпример** = данные, где правило падает; сохраняются, не отбрасываются.
- **Точность**: 0.43 → 1.00 (правило v1 → v2 на эталонном корпусе).
- **Реальный набор**: 45 запросов + 45 ответов, все `matched`, 100 % покрытия байт.
- **Фрейминг**: 10/10 потоков сфреймлены чисто через `payload`; два других
  кандидата, 0/10.
- **Тесты**: 957 всего; 620 без UI-тестов; 589 без UI и веб-наборов; CI зелёный.
- **Презентация**: 15 слайдов; последний слайд имеет два QR-кода, никогда слово
  «Вопросы».

Полные ответы: `docs/DEFENSE_FAQ.md`, `docs/FAQ_FOR_JUDGES.md`,
`presentation/Q_and_A.md`. Предполётный список: `docs/DEFENSE_CHECKLIST.md`.
