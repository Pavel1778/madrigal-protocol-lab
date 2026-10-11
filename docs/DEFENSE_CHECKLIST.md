# Defense checklist

A pre-flight list for the UMIRHack defense. Every item names the command or the
file that proves it, so a tick is a measurement, not a memory. Figures are from
the repository at the final revision; re-run the command if the branch has moved.

## За день до защиты

- [ ] `main = origin/main`, дерево чистое.
      `git fetch --all --prune && git status -sb && git log --oneline -1 origin/main`
- [ ] Тесты зелёные: `pytest tests/ -q` → **781 passed** (≈ 8 min).
- [ ] Линт чистый: `ruff check . --select "E4,E7,E9,F" --ignore E501` → All checks passed.
- [ ] Дека: `presentation/slides.pdf` и `presentation/slides-light.pdf` — по **19 страниц**;
      `presentation/slides.pptx` — 19 слайдов.
      `pdfinfo presentation/slides.pdf | grep Pages`
- [ ] QR открываются: `zbarimg -q presentation/public/qr_repo.png` и
      `qr_release.png` декодируются в репозиторий и в релиз `v1.0.0`.
- [ ] Релиз `v1.0.0` опубликован (не draft): 11 ассетов, включая
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
- [ ] Резервное видео `presentation/screencast.mp4` (2:05, H.264) проигрывается
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
- [ ] Записать разбор в `.agent-cache/` и в память проекта.

## Быстрый прогон одной строкой

```
git fetch --all --prune && git status -sb \
  && pytest tests/ -q \
  && ruff check . --select "E4,E7,E9,F" --ignore E501 \
  && pdfinfo presentation/slides.pdf | grep Pages \
  && gh release view v1.0.0 --json isDraft,assets
```

Expected: a clean tree at `origin/main`, 781 passed, lint clean, 19 pages, a
published release with 11 assets.
