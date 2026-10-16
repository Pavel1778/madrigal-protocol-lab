# Контракты форматов

Этот документ — единственный источник правды для данных, которыми обмениваются
три модуля проекта. Не меняйте ни одно имя поля или его смысл, не согласовав это
с сопровождающим, и повышайте `contract_version`, когда меняете.

Машиночитаемые определения лежат рядом с этим файлом:

- `docs/schemas/capture.schema.json` — нормализованный захват
- `docs/schemas/result.schema.json` — результат применения правила

Оба — JSON Schema черновика 2020-12.

## 1. Нормализованный захват

Создаёт движок захвата. Потребляют движок протокола и интерфейс.

```json
{
  "contract_version": 1,
  "capture_id": "sha256:<hash>",
  "source_file": "captures/cap1.pcapng",
  "sessions": [
    {
      "session_id": "s1",
      "endpoints": [
        { "ip": "...", "port": 0 },
        { "ip": "...", "port": 0 }
      ],
      "directions": {
        "A_to_B": {
          "bytes_b64": "...",
          "provenance": [
            { "offset": 0, "length": 4, "packet_index": 42, "seq": 1000, "ts": "..." }
          ],
          "diagnostics": [
            { "type": "gap", "offset": 100, "length": 8 }
          ]
        }
      }
    }
  ]
}
```

Замечания:

- `capture_id` — это `sha256:` и далее шестнадцатеричная контрольная сумма
  исходного файла захвата в нижнем регистре.
- `source_file` задан относительно корня проекта.
- `bytes_b64` — собранный направленный поток в base64. Пропуски не заполняются
  нулевыми байтами; недостающие диапазоны появляются в `diagnostics` с
  `type` = `gap`.
- `diagnostics[].type` — открытое множество. Дефекты потока используют `gap` и
  `ambiguity`; замечания парсера — `non_ip`, `non_tcp`,
  `ip_fragment_reassembled`, `ip_fragment_incomplete`, `ip_fragment_overlap`,
  `truncated_packet`, `truncated_frame` и `unsupported_linktype`.
  Потребители обязаны принимать типы, которых не знают.
  Каждая диагностика, указывающая на байты потока, несёт `offset` и `length`;
  замечания парсера могут нести вместо этого `packet_index`. `docs/CAPTURE_API.md`
  перечисляет каждый тип с его смыслом.
- Каждая запись `provenance` отображает диапазон байт потока (`offset`,
  `length`) на пакет, из которого он пришёл (`packet_index`, `seq`, `ts`).
  `packet_index` — индекс пакета в файле захвата в порядке чтения.
- `ts` — временная метка пакета в секундах эпохи.

## 2. Результат применения правила

Создаёт движок протокола. Потребляет интерфейс.

```json
{
  "contract_version": 1,
  "rule_id": "r1",
  "rule_version": 3,
  "capture_id": "...",
  "messages": [
    { "offset": 0, "length": 16, "fields": { "cmd": 4, "value": 21 }, "status": "matched" }
  ],
  "summary": { "matched": 205, "mismatched": 12, "unknown": 23, "uncovered": 0 }
}
```

Замечания:

- `rule_id` и `rule_version` определяют правило, создавшее результат.
- `messages[].offset` и `messages[].length` задают положение сообщения в
  направленном потоке.
- `messages[].fields` хранит раскодированные значения полей по имени поля.
- `messages[].status` — один из статусов, определённых в `result.schema.json`.
- `summary` считает сообщения по статусам.

## 3. Раскладка проекта на диске

Владелец — модуль интерфейса и проекта.

```
project.madrigal/
  manifest.json
  captures/
  logs/
  rules/
  results/
  annotations.sqlite
  reports/
```

Все пути внутри манифеста заданы относительно каталога проекта, чтобы проект
можно было перенести в другой каталог или на другую машину и по-прежнему открыть.
