---
theme: none
title: Лаборатория протоколов
info: |
  Восстановление недокументированного бинарного протокола поверх TCP.
  UMIRHack 2026, кейс #02, Мадригал.
class: text-left
highlighter: shiki
lineNumbers: false
drawings:
  persist: false
transition: slide-left
mdc: true
fonts:
  sans: Montserrat
  serif: Tektur
---

<div class="wrap-center">

# Лаборатория протоколов

<div class="subtitle">Исследование и описание неизвестного сетевого протокола поверх TCP</div>

<div class="meta">
Команда HTTP 418 · UMIRHack 2026 · кейс #02 · Мадригал<br>
Python 3.12 · PySide6 · dpkt · pytest · Docker
</div>

<svg class="logo" viewBox="0 0 256 256" role="img" aria-label="madrigal-protocol-lab">
  <rect width="256" height="256" rx="5" fill="#131516"/>
  <rect x="16" y="16" width="224" height="224" rx="5" fill="#1D1D1D"/>
  <g fill="none" stroke="#6D071F" stroke-width="10" stroke-linecap="square">
    <path d="M56 168 L56 96 M56 96 L96 136 L136 96 M136 96 L136 168"/>
    <path d="M176 96 L176 168 M176 132 L200 132"/>
  </g>
  <rect x="16" y="16" width="224" height="8" fill="#A2391D"/>
</svg>

</div>

---

# Задача: восстановить протокол, а не угадать его

<div class="cols">
<div>

- **Дано:** захваты (pcap/pcapng) и журнал действий устройства. Спецификации нет.
- **Нужно:** проверяемая интерпретация структуры сообщений.
- **Отличие от «просто распарсить»:** парсер даёт один ответ; здесь видно, где он верен, а где перестаёт работать.

</div>
<div class="card">

<span class="kpi">2</span>
<div class="kpi-label">входа: байты + журнал</div>
<hr>
<span class="kpi">3</span>
<div class="kpi-label">вопроса: что наблюдалось · где работает · почему это чтение</div>

</div>
</div>

<div class="caption">Выход — переносимая интерпретация с контрпримерами, привязанными к байтам.</div>

---

<div class="divider">

<div class="index">01</div>

# Подход

<div class="bar"></div>

</div>

---

# Три модуля, связанные JSON-контрактами

<img src="/assets/architecture.svg" alt="Архитектура" class="arch">

<div class="cols-3 mt-4">
<v-click><div class="card"><span class="tag">capture</span><br>pcap/pcapng → сессии → reassembly → provenance</div></v-click>
<v-click><div class="card"><span class="tag">protocol + hypothesis</span><br>фрейминг, поля, применение, контрпримеры, версии</div></v-click>
<v-click><div class="card"><span class="tag">ui</span><br>настольное окно PySide6</div></v-click>
</div>

<div class="caption">Контракты зафиксированы JSON Schema (draft 2020-12) и не меняются молча.</div>

---

<div class="divider">

<div class="index">02</div>

# Реализация

<div class="bar"></div>

</div>

---

# Захват потока: границы TCP ≠ границы сообщений

<div class="cols">
<div>

- Сессия — экземпляр соединения, а не пара адресов: повторное использование портов даёт новую сессию.
- Байты восстанавливаются по номерам последовательности; повторная передача даёт сведения о происхождении, а не лишние байты.
- Пропуск не заполняется нулями — становится диагностикой, сообщение поверх него помечается неполным.
- Клик по байту показывает пакет, номер последовательности и время: `packet 3 · seq 1001 · ts 1700000000.004`.

</div>
<div>

<div class="figure"><img src="/screenshots/01_main.png" alt="Главное окно"></div>
<div class="figure mt-2"><img src="/screenshots/09_provenance.png" alt="Происхождение байта"></div>
<div class="caption">Реальное окно: сессии, байты, интерпретация, происхождение и диагностика.</div>

</div>
</div>

---

# Правила и фрейминг: одно описание на весь поток

<div class="cols">
<div>

- Фрейминг: по длине, фиксированный размер, по маркерам, вручную.
- Типы полей: <span class="tag">uint</span><span class="tag">bytes</span><span class="tag">enum</span><span class="tag">string</span><span class="tag">checksum</span><span class="tag">computed</span>
- Поле с пометкой `hypothesis` — предположение о смысле, а не факт.
- Сообщения не перечисляются вручную: правило описывает весь поток.

</div>
<div>

```json
{
  "framing": {
    "type": "length_prefixed",
    "length_offset": 2, "length_size": 2,
    "byte_order": "big", "length_covers": "payload"
  },
  "fields": [
    {"name": "command", "offset": 0,
     "type": "uint8", "hypothesis": true,
     "expected": [1]}
  ]
}
```

</div>
</div>

<div class="caption">Фрагмент `examples/corpus_rule_v1.json`.</div>

---

# Гипотезы и контрпримеры: совпадение — не доказательство

<div class="cols">
<div>

Шесть статусов по каждому сообщению:

<div class="mt-2">
<span class="status-matched">■ matched</span> · <span class="status-mismatched">■ mismatched</span> · <span class="status-ambiguous">■ ambiguous</span><br>
<span class="tag">incomplete</span><span class="tag">uncovered</span><span class="tag">not_applicable</span>
</div>

`mismatched` — это контрпример, привязанный к байтам и к пакету-источнику.

- Правило проверяется на **всём** корпусе.
- Контрпримеры **сохраняются**, а не отбрасываются.

</div>
<div>

<div class="figure"><img src="/screenshots/05_validation.png" alt="Контрпример"></div>
<div class="figure mt-2"><img src="/screenshots/04_hex_gap.png" alt="Пропуск в потоке"></div>

</div>
</div>

---

<div class="divider">

<div class="index">03</div>

# Демонстрация

<div class="bar"></div>

</div>

---

# Цикл на корпусе: шесть шагов

<img src="/assets/research_timeline.svg" alt="Таймлайн исследования" class="w-full mt-8">

<div class="mt-8">

<v-click>

1. **Наблюдение:** байты запроса начинаются с `01 00 00 01`.
2. **Гипотеза:** по смещению 2 — длина два байта, старший вперёд.

</v-click>
<v-click>

3. **Проверка:** правило разбирает все потоки без остатка.
4. **Контрпример:** встречаются команды `2` и `3`, а правило допускало только `1`.

</v-click>
<v-click>

5. **Уточнение:** множество команд расширено до `1`, `2`, `3`.
6. **Повторная проверка:** контрпримеров нет.

</v-click>

</div>

---

# Проверка и контрпримеры: точность 0.43 → 1.00

<div class="cols">
<div>

<div class="figure"><img src="/screenshots/10_hypotheses.png" alt="Гипотезы"></div>
<div class="caption">Чтение, объявленное правилом v1, даёт 0.43 (60 support, 80 contradict).</div>

</div>
<div>

<v-click>
<img src="/assets/precision_v1_v2.svg" alt="Precision" class="w-full">

| показатель | v1 | v2 |
| --- | --- | --- |
| matched | 60 | 140 |
| mismatched | 80 | 0 |
| precision | 0.43 | 1.00 |

<div class="caption">Источник: `docs/METRICS.md`.</div>
</v-click>

</div>
</div>

---

# Сравнение версий: изменён один список, структура та же

<div class="cols">
<div>

<img src="/assets/framing_payload.svg" alt="Фрейминг" class="w-full">

<div class="caption">Фрейминг `payload` разбирает 10/10 потоков; два других кандидата — 0/10.</div>

</div>
<div>

<div class="figure"><img src="/screenshots/08_diff.png" alt="Diff версий"></div>

- Изменён **только** список допустимых команд: `[1]` → `[1, 2, 3]`.
- Фрейминг, число полей, смещения и типы идентичны.
- Старый результат хранится со своей версией и помечается `outdated`.

</div>
</div>

---

# Контрпример как ценность: байт, который уточнил правило {#control-example}

<div class="cols">
<div>

**Конкретный `mismatched`-байт:**

| поле | значение |
| --- | --- |
| session / direction | `s2` / `A_to_B` |
| message offset | `0`, length `7` |
| bytes | `02 00 00 03 13 00 55` |
| reason | `value 2 not in expected [1]` |
| packet / seq | `128` / `20001` |

</div>
<div>

<v-click>

**Как уточнили правило:**

```diff
 { "name": "command", "offset": 0,
   "type": "uint8", "hypothesis": true,
-  "expected": [1] }
+  "expected": [1, 2, 3] }
```

<div class="card mt-4">

Один байт, привязанный к пакету-источнику, превратил 80 контрпримеров в 0 (v1 → v2).

</div>
</v-click>

</div>
</div>

---

# Метрики: сводка чисел

<div class="cols">
<div>

<div class="cols">
<div><span class="kpi">140</span><br><span class="kpi-label">matched, rule v2</span></div>
<div><span class="kpi">0</span><br><span class="kpi-label">counterexamples, v2</span></div>
</div>
<div class="cols mt-4">
<div><span class="kpi">10/10</span><br><span class="kpi-label">потоков разобрано</span></div>
<div><span class="kpi">280</span><br><span class="kpi-label">сообщений в захвате 01</span></div>
</div>
<div class="cols mt-4">
<div><span class="kpi">40/40</span><br><span class="kpi-label">перенос на захват 02</span></div>
<div><span class="kpi">5/5</span><br><span class="kpi-label">CI зелёный</span></div>
</div>

<div class="caption mt-4">Источник: `docs/METRICS.md`, `docs/AUDIT.md`.</div>

</div>
<div>

<img src="/assets/coverage_donut.svg" alt="Покрытие корпуса" class="w-full">
<img src="/assets/memory_sweep.svg" alt="Свип памяти" class="w-full mt-2">

</div>
</div>

---

<div class="divider">

<div class="index">04</div>

# Итог

<div class="bar"></div>

</div>

---

# Ограничения: честный список

<div class="cols">
<div>

1. Смысл байта флагов не установлен: в корпусе он постоянен.
2. Поле значения не объяснено ни одним проверенным чтением и остаётся гипотезой.
3. Ответы разбираются по границам, но не по полям.

</div>
<div>

4. Альтернативные чтения берутся из заданного набора: смысл вне набора не будет найден.
5. Корпус синтетический — протокол может не совпадать с реальным устройством.

<div class="card mt-6">

**Интерпретация верна для проверенных захватов и молчит вне них.**

</div>

</div>
</div>

---

# Итог и ссылки

<div class="cols">
<div>

- Восстановлена раскладка: код команды, флаги, длина (`uint16`, BE), полезная нагрузка.
- Команда принимает `1`, `2`, `3`; смещение 4 — идентификатор параметра; 5–6 — значение при записи.
- Правило переносится на второй захват и **не** переносится на посторонний.
- Каждое утверждение подкреплено байтами, контрпримером или журналом.

</div>
<div class="text-center">

<img src="/qr_repo.png" alt="QR: репозиторий" class="w-56 mx-auto">

<div class="caption">github.com/Pavel1778/madrigal-protocol-lab</div>

<div class="mt-4 text-sm">
REPORT.md · docs/REFERENCE_INVESTIGATION.md · docs/demo.md
</div>

</div>
</div>

---

<div class="wrap-center text-center">

# Вопросы

<div class="subtitle">Команда HTTP 418 · UMIRHack 2026</div>

<div class="meta">github.com/Pavel1778/madrigal-protocol-lab</div>

</div>
