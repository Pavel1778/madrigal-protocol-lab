# Чек-лист защиты

Английский оригинал: [DEFENSE_CHECKLIST.md](../DEFENSE_CHECKLIST.md).

Предполётный список к защите UMIRHack. Каждый пункт называет команду или файл,
которые его доказывают, поэтому галочка — это измерение, а не память. Числа — из
репозитория на финальной ревизии; перезапустите команду, если ветка сдвинулась.

## За день до защиты

- [ ] `main = origin/main`, дерево чистое.
      `git fetch --all --prune && git status -sb && git log --oneline -1 origin/main`
- [ ] Тесты зелёные: `pytest tests/ -q` → **957 passed** на текущем `main`
      (`acea1d8`; Python 3.13, PySide6 6.8.1, `QT_QPA_PLATFORM=offscreen`;
      на теге `v1.0.0`, который лежит в сдаваемом архиве, — **794 passed**; ≈ 8 min).
      UI-тесты требуют Qt-runtime; в контейнере без `libEGL.so.1` полный набор
      не собирается — там `pytest --ignore=tests/ui` → **620 passed**.
      Указывайте число с контекстом: 620 без UI, 957 с Qt.
- [ ] Линт чистый: `ruff check .` → All checks passed.
- [ ] Дека: `presentation/slides.pdf` и `presentation/slide-light.pdf` — по **15 страниц**;
      `presentation/slide.pptx` — 15 слайдов.
      `pdfinfo presentation/slides.pdf | grep Pages` (нужен `poppler-utils`);
      без него слайды PPTX считаются стандартной библиотекой:
      `python -c "import zipfile;z=zipfile.ZipFile('presentation/slide.pptx');print(len([n for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')]))"`
- [ ] QR открываются: `zbarimg -q presentation/public/qr_repo.png` и
      `qr_release.png` декодируются в репозиторий и в релиз `v1.0.0`.
- [ ] Релиз `v1.0.0` опубликован (не draft): 12 ассетов, включая
      `submission_*.zip`, `slides.pdf` и `.deb`.
      `gh release view v1.0.0 --json isDraft,assets`
- [ ] Ссылки в форме сдачи открываются в инкогнито (без входа в аккаунт).
- [ ] Числа сверены с `docs/METRICS.md`, `docs/REAL_CORPUS_ANALYSIS.md`,
      `docs/AUDIT.md` — ни одного придуманного числа.

## Репетиция

- [ ] `presentation/defense_script.md`, 5-минутный маршрут прогнан с таймером
      (бюджет ≈ 3:57).
- [ ] `presentation/defense_script.md`, 10-минутный маршрут прогнан с таймером
      (бюджет ≈ 5:44).
- [ ] Резервное видео `presentation/screencast.mp4` (3:40, H.264) проигрывается
      без звука и без сети.
- [ ] `docs/demo.md` и `docs/demo_cli.md` пройдены вслух, окно поднимается на
      эталонном экспорте.
- [ ] Ответы из `docs/FAQ_FOR_JUDGES.md` и `docs/DEFENSE_FAQ.md` проговорены.

## В день защиты

- [ ] PDF загружен в личный кабинет до 12:00.
- [ ] Капитан загрузил README в форму до 11:00.
- [ ] GUI и веб-страница открыты и проверены до выступления.
- [ ] Резервный видеофайл готов на случай, если экран не поднимется.
- [ ] Известны ответы на 10 частых вопросов (`docs/FAQ_FOR_JUDGES.md`).

## После защиты

- [ ] Забрать обратную связь организаторов.
- [ ] Отозвать любой временный токен, если он ещё активен (см. `docs/GIT_HYGIENE.md`).
- [ ] Записать разбор в `.scratch/` и в память проекта.

## Быстрый прогон одной строкой

```
git fetch --all --prune && git status -sb \
  && pytest tests/ -q \
  && ruff check . \
  && pdfinfo presentation/slides.pdf | grep Pages \
  && gh release view v1.0.0 --json isDraft,assets
```

Ожидается: чистое дерево на `origin/main`, 957 passed на текущем `main`
(794 на теге `v1.0.0`), линт чистый, 15 страниц, опубликованный релиз с 14
ассетами.
