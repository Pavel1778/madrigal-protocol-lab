# Presentation verification

Read-only verification of the submission deck, the screencast and the demo
driver against the nine requirements from the organizers. Artifact under
examination: `presentation/slides.md` and the committed `presentation/slides.pdf`
at revision `1c8621f`. Nothing was rebuilt and no history was rewritten.

Reproduce any line below with the command in the same row.

## Deck

| fact | value | command |
| --- | --- | --- |
| pages in the committed PDF | 22 | `pdfinfo presentation/slides.pdf` |
| page size | 735.12 x 414 pts, 16:9 | `pdfinfo presentation/slides.pdf` |
| slides in the source | 22 | `grep -c '^---$' presentation/slides.md` |
| producer | pdf-lib | `pdfinfo presentation/slides.pdf` |

The source and the PDF agree on the set of slides. The one ordering difference
is the team slide: `slides.md` places it second, the committed PDF places it on
page 5. Both carry all 22 slides; only the position differs. The PDF was
exported from an earlier revision of `slides.md`, before the title and section
divider slides were inserted ahead of the team slide. To remove the difference,
re-export once with `presentation/export_pdf.sh`.

Per-page headings, from `pdftotext -layout presentation/slides.pdf`:

    1  Лаборатория протоколов
    2  Задача: восстановить протокол, а не угадать его
    3  01 Подход
    4  Три модуля, связанные JSON-контрактами
    5  Состав команды
    6  02 Реализация
    7  Захват потока: границы TCP ≠ границы сообщений
    8  Правила и фрейминг: одно описание на весь поток
    9  Гипотезы и контрпримеры: совпадение — не доказательство
    10 Функционал: три киллер-фичи
    11 03 Демонстрация
    12 Цикл на корпусе: шесть шагов
    13 Проверка и контрпримеры: точность 0.43 → 1.00
    14 Сравнение версий: изменён один список, структура та же
    15 Контрпример как ценность: байт, который уточнил правило
    16 Метрики: сводка чисел
    17 Расширения: веб-интерфейс на localhost поверх того же ядра
    18 04 Итог
    19 Ограничения: честный список
    20 Направления развития
    21 Итог и ссылки
    22 Вопросы

No page is blank; each carries a heading.

## The nine organizer requirements

| # | requirement | present | slides.md | PDF page |
| --- | --- | --- | --- | --- |
| 1 | Тема | yes | 1 | 1 |
| 2 | Состав команды с фото и ролями | yes | 2 | 5 |
| 3 | Технический стек | yes | 1, 4 | 1, 4 |
| 4 | Архитектура | yes | 4 | 4 |
| 5 | Функционал и киллер-фичи | yes | 10 | 10 |
| 6 | Скриншоты или скринкаст | yes | 7, 9, 13, 14, 17 | 7, 9, 13, 14, 17 |
| 7 | QR на GitHub | yes | 21 | 21 |
| 8 | Демонстрация отдельным блоком | yes | 11–16 | 11–16 |
| 9 | Направления развития | yes | 20 | 20 |

Nine of nine present.

- Requirement 2: the `.team` block renders `public/team-avatar.png` (640x640,
  real PNG) beside both entries — «Сабадаш Павел» with the architecture,
  capture, project, report, coordination, backend and GUI role, and «Предков
  Никита» with the backend, rules and tests role.
- Requirement 3: the stack line «Python 3.12 · PySide6 · dpkt · pytest ·
  Docker» sits on the title slide; the architecture slide repeats the module
  breakdown. The list is distributed, not on a dedicated slide.
- Requirement 6: six GUI screenshots plus the web screenshot, and the committed
  screencast.
- Requirement 7: `public/qr_repo.png` (410x410) is referenced by the closing
  slide.

Every image reference resolves. `grep -oE '(src|href)="[^"]+"'` over `slides.md`
yields six `/assets/*.svg`, six `/screenshots/*.png`, and `/qr_repo.png`,
`/team-avatar.png`, `/web.png`; each is present under `presentation/assets`,
`presentation/screenshots` or `presentation/public`.

## Team slide styling

`presentation/style.css` defines `.team` (line 276), `.team-avatar` (line 283)
and `.team-info` (line 291). `slides.md` uses each class on the team slide. The
markup and the stylesheet match; no fix is needed.

## Screencast

| fact | value | command |
| --- | --- | --- |
| committed file | `presentation/screencast.mp4` | `git ls-files presentation/screencast.mp4` |
| codec, size | H.264, 1920x1080, 15 fps | `ffprobe presentation/screencast.mp4` |
| duration | 166 s (2:46) | `ffprobe presentation/screencast.mp4` |
| bytes | 1 164 093 | `ffprobe presentation/screencast.mp4` |

The guide `presentation/VIDEO.md` line 118 describes the committed clip as «the
shorter 1:25 clip». The committed file is 2:46, not 1:25; the 1:25 figure
belongs to an intermediate take, not the file that ships. The description should
be corrected to 2:46, or the clip trimmed to 1:25 if the shorter length is the
intent. Video content was not modified here.

`presentation/video.mp4` is present locally (219 s, 3.7 MB) and gitignored as a
large binary; it is rebuilt from `VIDEO.md`.

## Demo driver

`presentation/record_demo.py` drives the real window through
`open_default_window`, `load_rule` and `apply_rule`, and pauses between steps so
the take reads as a demonstration. It adds nothing to the product: it is a
recording aid and imports only the public window entry points. No instruction,
tool or model name appears in the file.

## Text hygiene

- No `TODO`, `FIXME`, `XXX` or `HACK` in the source, tests, scripts or docs held
  in the repository.
- No token, key or credential appears anywhere in the working tree or history.
  `ghp_` and `github_pat_` occur only inside the audit documents that describe
  the scan itself.
- The deck, the docs and the code name no assistant, model or generator.

## Outstanding

1. Re-export `presentation/slides.pdf` so the team slide moves to page 2 and the
   PDF order matches `slides.md`.
2. Correct the clip length in `presentation/VIDEO.md` line 118 (2:46, not 1:25)
   or trim the clip, whichever the defense uses.
