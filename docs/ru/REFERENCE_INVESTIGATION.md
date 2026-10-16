# Эталонное исследование

Английский оригинал: [REFERENCE_INVESTIGATION.md](../REFERENCE_INVESTIGATION.md).

## Наблюдения

- Корпус: corpus_capture_01.pcapng (capture_id sha256:1a2f3637124abcd43049bdf9432ae3d18024276cf7de29efd43562e0c61f272c).
- Область правила v1: A_to_B.
- Сфреймлено сообщений: 280.
- Счётчики: matched=60, mismatched=80, incomplete=0, ambiguous=0, uncovered=0, not_applicable=140, outdated=0, unknown=0
- Первые байты основного захвата, как наблюдение, из которого читалась раскладка:

```
s1 A_to_B: 010000011001000001110100000112010000011001000001
```

## Фрейминг

Поле длины — на смещении 2, два байта, big-endian. Что оно считает, не записано,
поэтому три кандидата фреймятся против реальных байтов. Кандидат сохраняется только
если он фреймит каждый поток без остаточных байтов, без обрезанного последнего
сообщения и без невозможного байта команды.

| захват | поток | байт | payload | payload_and_length_field | entire_message |
| --- | --- | --- | --- | --- | --- |
| corpus_capture_01.pcapng | s1 A_to_B | 300 | 60 msgs, 300/300 B, чисто | 1 msgs, 0/300 B, сломано | 1 msgs, 0/300 B, сломано |
| corpus_capture_01.pcapng | s1 B_to_A | 420 | 60 msgs, 420/420 B, чисто | 3 msgs, 420/420 B, сломано | 1 msgs, 0/420 B, сломано |
| corpus_capture_01.pcapng | s2 A_to_B | 420 | 60 msgs, 420/420 B, чисто | 2 msgs, 420/420 B, сломано | 1 msgs, 0/420 B, сломано |
| corpus_capture_01.pcapng | s2 B_to_A | 420 | 60 msgs, 420/420 B, чисто | 2 msgs, 420/420 B, сломано | 1 msgs, 0/420 B, сломано |
| corpus_capture_01.pcapng | s3 A_to_B | 100 | 20 msgs, 100/100 B, чисто | 1 msgs, 0/100 B, сломано | 1 msgs, 0/100 B, сломано |
| corpus_capture_01.pcapng | s3 B_to_A | 1376 | 20 msgs, 1376/1376 B, чисто | 3 msgs, 1376/1376 B, сломано | 2 msgs, 1376/1376 B, сломано |
| corpus_capture_02.pcapng | s1 A_to_B | 100 | 20 msgs, 100/100 B, чисто | 1 msgs, 0/100 B, сломано | 1 msgs, 0/100 B, сломано |
| corpus_capture_02.pcapng | s1 B_to_A | 140 | 20 msgs, 140/140 B, чисто | 2 msgs, 140/140 B, сломано | 1 msgs, 0/140 B, сломано |
| corpus_capture_02.pcapng | s2 A_to_B | 140 | 20 msgs, 140/140 B, чисто | 2 msgs, 140/140 B, сломано | 1 msgs, 0/140 B, сломано |
| corpus_capture_02.pcapng | s2 B_to_A | 140 | 20 msgs, 140/140 B, чисто | 2 msgs, 140/140 B, сломано | 1 msgs, 0/140 B, сломано |

Только `payload` фреймит все 10 потоков без остаточных байтов и без обрезанного
сообщения. Два других кандидата либо останавливаются после первого размера, либо
разбивают поток на горстку завышенных блоков, поэтому они отвергнуты.

## Контрпримеры

80 контрпримеров против правила v1:

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
- ... и ещё 68 того же вида (каждый — байт команды вне ожидаемого набора).

## Уточнение

Правило уточнено до v2. Изменения:

- поле command: expected [1] -> [1, 2, 3]

Счётчики после уточнения: matched=140, mismatched=0, incomplete=0, ambiguous=0, uncovered=0, not_applicable=140, outdated=0, unknown=0.

## Различение версий

Правило v1 и правило v2 — разные правила над одними и теми же байтами: в захвате
ничего не изменилось, только его описание. Счётчики ниже — из повторного прогона
обеих версий.

| метрика | v1 | v2 | дельта |
| --- | --- | --- | --- |
| matched | 60 | 140 | +80 |
| mismatched | 80 | 0 | -80 |
| контрпримеры | 80 | 0 | -80 |
| покрытие | 0.5 | 0.5 | +0.0 |
| точность | 0.428571 | 1.0 | +0.571429 |
| counterexample_density | 57.142857 | 0.0 | -57.142857 |

Разрешено контрпримеров: 80.
Внесено контрпримеров: 0.
Дельта покрытия: +0.0.

Изменение правила никогда не переписывает байты, против которых оно проверялось.
Результат v1 остаётся на диске со своей версией правила; читатель видит, какая
версия произвела какой вердикт.

## Уточнённое правило

Уточнённое правило записано в `corpus_rule_v2.json`, чтобы его можно было применить
снова из CLI, не выводя заново.

## Применимость

Правило v2, применённое к corpus_capture_02.pcapng (capture_id sha256:4aa281b97de9afa09d74ff0f5c41e9f6c4fc2b7b07ddf314f33b55d2fec95afc).
Счётчики: matched=40, mismatched=0, incomplete=0, ambiguous=0, uncovered=0, not_applicable=40, outdated=0, unknown=0.
Контрпримеры: 0.

## Граница применимости

Правило v2, применённое к synthetic_live.pcapng — захвату, произведённому настоящим
стеком TCP с намеренно другой раскладкой (little-endian длина, байт id транзакции,
команды 0x21/0x22/0x23). Правило никогда не подгонялось под этот трафик.

- s1 A_to_B: 61 B -> 1 messages, 61/61 B, truncated
- s1 B_to_A: 116 B -> 1 messages, 116/116 B, truncated

Потоков сфреймлено чисто: 0/2.
Счётчики: matched=0, mismatched=0, incomplete=1, ambiguous=0, uncovered=0, not_applicable=1, outdated=0, unknown=0
Контрпримеры: 1.

Big-endian длина и другой набор команд означают, что правило не переносится: его
совпадения здесь случайны, а не доказательны. Это граница применимости правила, и она
заявлена, а не скрыта повторной настройкой до тех пор, пока что-нибудь не совпадёт.

## Корреляция с журналом

Журнал: 185 записей; временная метка — время захвата пакета-запроса. Каждый
сфреймленный запрос сопоставляется с ближайшей записью внутри окна 500 мс.

| захват | направление | запросов | скоррелировано | несопоставленных запросов | несопоставленных записей | target=parameter | value=result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| corpus_capture_01.pcapng | A_to_B | 140 | 140 | 0 | 45 | 140 | 0/0 |
| corpus_capture_02.pcapng | A_to_B | 40 | 40 | 0 | 145 | 40 | 0/0 |

Каждый запрос попадает на запись журнала с той же временной меткой, а поле `target`
разрешается в параметр, который журнал называет для каждого скоррелированного
запроса. Поле `value` присутствует только там, где запрос несёт записанное значение;
ожидаемый `result` держится только для несопоставленных записей, поэтому различающееся
значение сохраняется как доказательство против поля, а не скрывается.

## Альтернативные чтения

Поля, помеченные `hypothesis: true`, названы по догадке. Каждое оценивается против
конкурирующих чтений по сфреймленному корпусу; объявленный смысл — один кандидат и
может проиграть. Балл — support / (support + contradict).

Поле `command` (140 значений):

| чтение | поддержка | противоречий | балл |
| --- | --- | --- | --- |
| entropy_enum | 140 | 0 | 1.00 |
| low_cardinality | 140 | 0 | 1.00 |
| offset_shift_+1 | 140 | 0 | 1.00 |
| counter | 137 | 2 | 0.99 |
| constant | 60 | 80 | 0.43 |
| message_length | 0 | 140 | 0.00 |
| remaining_length | 0 | 140 | 0.00 |

Лучшее соответствие: `entropy_enum`.

Поле `target` (140 значений):

| чтение | поддержка | противоречий | балл |
| --- | --- | --- | --- |
| low_cardinality | 140 | 0 | 1.00 |
| constant | 20 | 120 | 0.14 |

Лучшее соответствие: `low_cardinality`.

Поле `value` (60 значений):

| чтение | поддержка | противоречий | балл |
| --- | --- | --- | --- |
| entropy_parameter | 60 | 0 | 1.00 |
| constant | 1 | 59 | 0.02 |
| message_length | 1 | 59 | 0.02 |
| remaining_length | 0 | 60 | 0.00 |

Лучшее соответствие: `entropy_parameter`.

## Открытые вопросы

- Смыслы полей, помеченные `hypothesis: true`, остаются предположениями; правило,
  которое совпадает, — не доказательство.
- Поведение вне проверенных захватов неизвестно; правило подтверждено только внутри
  проверенной области.

## Ограничения

- Правило описывает только направление запроса; ответы фреймятся, но не
  интерпретируются по полям.
- Смыслы полей, помеченные `hypothesis: true` (enum `target`, нагрузка `value`),
  остаются предположениями. Совпадение — не доказательство.
- Вопрос фрейминга решён против корпуса; поток, чьё поле длины считает что-то другое,
  потребовал бы нового правила.
- Диагностики неоднозначности и пропуска показываются, никогда не заполняются нулями,
  поэтому сообщение над пропуском сообщается как `incomplete`, а не угадывается.
- Синтетический живой захват не делит раскладку байт с корпусом, поэтому здесь ничто
  не заявлено как обобщающееся на него.
