# Журнал изменений

Английский оригинал: [CHANGELOG.md](../../CHANGELOG.md).

Краткая запись работы над стадиями захвата, проекта и отчёта, по итерациям.
Коммиты — Conventional Commits; короткие хеши — из стадии захвата.

## Итерация 1 — движок захвата

Чтение PCAP/PCAPNG, идентификация TCP-сессий, направленная пересборка, провенанс
байт и выгрузка нормализованного захвата.

- `465e93c` feat(capture): add pcap/pcapng parsing, sessions, reassembly
- `b845787` test(capture): cover parser, sessions, reassembly and export

## Итерация 2 — корпус и бенчмарки

Исследовательский корпус с его журналом действий и первый бенчмарк ресурсов.

- `274e16e` feat(capture): add research corpus and its journal
- `6674117` perf(capture): benchmark the engine on the reference profile
- `1d002ce` docs(capture): document the API and the integration seam

## Итерация 3 — потоковый режим и обработка дефектов

Потоковая нормализация для больших захватов, фикстуры дефектов и выгрузка
пересобранных потоков в pcap.

- `ddab671` perf(capture): add streaming mode for large captures
- `057194d` test(capture): cover deformed pcap and pcapng fixtures
- `f204b2d` feat(capture): export reassembled streams as pcap
- `78e5b48` docs(capture): record the diagnostic set and the pcap export
- `0134798` feat(capture): add a synthetic stand with a real TCP exchange

## Итерация 4 — интеграция, проект, отчёт

Интеграционные тесты корпуса, закоммиченные эталонные выгрузки, контейнер
переносного проекта и отрисовщики отчёта.

- `9e2cd07` test(capture): add corpus integration tests
- `6dd72a5` chore(corpus): add reference export
- `ea25583` feat(project): add portable project container
- `1970ae6` feat(report): add markdown and html rendering
- `442835c` docs: finalize readme, architecture, and capture api

## Итерация 5 — конвейер CLI, бенчмарки, использование

Команда сквозного конвейера, развёртка по размерам и разбивка фаз в бенчмарке и эта
документация.

- `55313bf` fix(gitignore): un-ignore tests/corpus
- `069eda8` feat(project): add end-to-end pipeline CLI
- `40a7253` perf(capture): expand benchmarks by phase and size
- docs: add usage walkthrough and changelog

## Итерация 6 — аудит, CI, сдача

Аудит репозитория с граничными тестами, более широкий CI, сборщик сдачи и отчёт о
переносимости.

- `87c71a2` docs: add repository audit
- `a296b0d` test: cover capture, project, and report boundaries
- `245bece` ci: add python matrix and code-quality jobs
- `029ae96` chore: hygiene pass on repository
- `3cf0b33` feat(scripts): add submission builder
- `92d2762` docs: add portability report
- `43694ad` docs: extend the integration checklist

## Итерация 7 — интеграция протокола и пересмотр CI

Ветка протокола и окна слита в `main`, а линт-гейт сужен до стартового набора
правил, чтобы общая ветка была зелёной.

- `a5535e0` merge(protocol): verify branch, screenshots, lint fixes
- `779238c` merge: verify branch, lint fixes, CI rescope
- `1c86f10` chore(ci): rescope code-quality to starter ruleset
- `308b62c` docs(audit): record CI rescope and integration merge

## Итерация 8 — сдача, контейнер, материал защиты

Архив сдачи, образ контейнера и числа и решения для защиты.

- `e70bfd8` docs: add submission metadata and delivery formats
- `cbb4b48` fix(submission): include examples directory in the archive
- `87e722f` docs: add submission metadata and portability check
- `29451c7` feat(docker): add container image and update portability notes
- `c5b9cd2` docs: add metrics, roadmap and architecture decisions

## Итерация 9 — установщики, презентация, изоляция тестов

Ветка упаковки, презентация защиты и независимые от локали тесты интерфейса. Это
работа после тега `v1.0.0`.

- `b192531` fix(packaging): ship Qt runtime libs in the image and the whole package tree in the wheel
- `116e64b` docs: install guide for every format, delivery table, Docker in BINARY
- `bc7d315` test(project): cover packaging scripts and record video measurement
- `540e5fd` feat(presentation): team, killer features, web and roadmap slides, reserve video
- `84362b8` test(ui): isolate window tests from the developer QSettings and locale

## Итерация 10 — покрытие тестами интерфейса и проверка

Наборы тестов интерфейса, матрица CI, которая их гоняет, и консолидированная проверка
деки, скринкаста и драйвера демонстрации.

- `4c3b1a3` chore(repo): add git attributes, hook, message template and hygiene doc
- `1c8621f` test(ui): add locale, snapshot and state-isolation suites

## Не выпущено

Всё, слитое в `main` после тега `v1.0.0`, по pull request. `v1.0.0` — слияние PR #14
(`f637644`); записи ниже — работа, что последовала.

### Добавлено

- Покрытие тестами интерфейса и матрица CI для него: наборы локали, снимков,
  изоляции состояния и раскладки, и работа `ui` (PR #18).
- Перцептивное сравнение снимков для интерфейса, заменяющее точную попиксельную
  базовую линию, которая ломалась на каждом изменении хинтинга шрифта (PR #18).
- Набор захватов организатора, закоммиченный в `tests/corpus/real/`, с правилами
  термостенда в `examples/` и журналом действий CSV (PR #20).
- `scripts/investigate_dataset.py`, пересобирающий `docs/DATASET_INVESTIGATION.md` из
  предоставленных захватов (PR #20).
- Фиксированное смещение заголовка во фрейминге длины (`length_bias`) и условие на
  любое поле, что понадобилось протоколу термостенда (PR #20).
- Полоса легенды состояний байтов над hex-просмотром (`src/ui/legend.py`):
  сворачиваемая легенда, где каждый образец закрашен той же кистью, что и байты,
  которые обозначает, и поясняет своё состояние при наведении (PR #72).
- Светлая тема для деки и сайта и резервное видео `presentation/screencast.mp4`
  (PR #21, PR #23).
- `docs/DEFENSE_CHECKLIST.md` и `docs/FAQ_FOR_JUDGES.md` для защиты (PR #26).
- `docs/DEMO_CHEATSHEET.md` (одностраничник для печати к демонстрации) и
  `presentation/Q_and_A.md` (пятнадцать вопросов защиты в сжатой форме), связанные из
  списка документов README.
- Дека несёт Tektur, Montserrat и JetBrains Mono, встроенные в HTML, поэтому она
  отрисовывает собственные шрифты на машине, где ни один из них не установлен.
- Типы полей `float`, `varint`, `tlv` и битовые поля, декодируемые движком правил и
  покрытые схемой правил.
- Выгрузка результата в CSV и JSONL: `write_result` выбирает формат по суффиксу
  вывода, наряду с контрактным JSON.
- Связывание запроса и ответа (`src/hypothesis/pairing.py`): ходы несут уверенность и
  наблюдения, на которых она держится, а CLI протокола получил подкоманду `pair`.
- Заметки исследователя, хранимые в проекте (`src/project/annotations.py`), с
  подкомандами `annotate` и `annotations` и разделом Annotations в обоих отрисовщиках
  отчёта.

### Изменено

- Дека была пересобрана как редактируемый нативный текст PPTX с нарастаниями по клику,
  затем сокращена до девятнадцати слайдов с разнообразными раскладками и без
  переполнения (PR #16, PR #21, PR #25).
- Финальный проход урезал анимации до не более трёх нарастаний по клику на слайд и
  простого перехода-затухания везде; обложка, разделители секций, слайд записи и
  закрывающий слайд теперь статичны. Значок воспроизведения слайда записи переехал в
  маркер 40 px в правом нижнем углу, метрическая заметка указывает, что бюджет 4 ГиБ
  на машине с 16 ГиБ, а подписи и метки PPTX подняты до 14 pt.
- Спикерский сценарий защиты разделён на маршрут на 5 минут и на 10 минут с таймингами,
  выведенными из произносимого текста (PR #24).
- Счётчики тестов по документации обновлены до слитой ревизии, а дека и документы
  проверки синхронизированы с 15-слайдовой декой (PR #16, PR #18, PR #25, PR #26, PR #70).
- README, аудит, отчёт о переносимости и проверка презентации теперь цитируют 794 теста
  и опубликованный архив `v1.0.0` (PR #26).

### Исправлено

- Интерфейс теперь помещается в небольших окнах, а русские подписи полны, включая
  имена тем в настройках (PR #17).
- Переполнение деки и длина резервного клипа исправлены (PR #16, PR #23).
- Подпись колонки ASCII над hex-просмотром откатывалась к пропорциональному шрифту
  основного текста и уезжала от колонки, которую называет; теперь она рисуется тем же
  моноширинным шрифтом, что и байты, а легенда состояний стала компактной полосой
  (PR #72).
- Устаревший предел «захваты организатора недоступны» заменён состоянием «получены и
  разобраны» (PR #20, PR #26).

### Удалено

- Слитые ветки-функции вычищены после того, как работа по набору данных легла в `main`
  (PR #20).
- Скачанные браузером архивы `sample_protocol.tar*`, оставленные в корне репозитория;
  сам набор данных закоммичен в `tests/corpus/real/`, а дубликаты игнорируются.
