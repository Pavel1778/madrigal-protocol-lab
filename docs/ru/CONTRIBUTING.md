# Участие в разработке

Как вносятся изменения в этот репозиторий. Это небольшая команда на
фиксированном расписании хакатона, поэтому правила короткие и проверяются CI.

## Настройка

```
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Ветки

- `main` содержит собранный проект. Не пушить в неё напрямую; открывайте pull
  request.
- Работайте в короткоживущей ветке, названной по области, например
  `capture/tcp-reassembly` или `protocol/field-types`. Удаляйте её после слияния.

## Коммиты

Conventional Commits, на английском, тема не длиннее 72 символов, повелительное
наклонение.

```
feat(capture): implement TCP stream reassembly
test(protocol): cover incomplete message framing
fix(ui): keep hex selection after a theme switch
docs(readme): note the portable project layout
```

Область называет участок (`capture`, `protocol`, `hypothesis`, `ui`, `project`,
`report`, `docs`, `ci`). Один логический изменение на коммит.

## Перед push

Прогоните проверки локально; CI запускает те же самые.

```
QT_QPA_PLATFORM=offscreen pytest tests/ -q
ruff check .
```

CI также проверяет зависимости (`pip-audit` под `.[dev]`). `ruff format --check`
и `mypy .` отложены для модулей вне текущего изменения, как записано в
`docs/AUDIT.md`; запускайте их по файлам, которые трогаете.

- Все тесты проходят. Новое поведение идёт с тестом на реальных байтах и реальном
  движке, а не на заглушке.
- Никаких `TODO`, `FIXME`, закомментированного кода или отладочного вывода.
- Никаких секретов, персональных данных и крупных бинарников вне `presentation/`.
- Не коммитить `.venv/`, `__pycache__/`, `*.pcap` вне `tests/fixtures/`, локальный
  `project.madrigal/` или `.env`. `.gitignore` закрывает всё это.

## Pull request

- Заголовок в стиле коммита выше.
- Укажите, что изменилось, почему и как проверено (команда, которую запустили).
- Не сливайте собственный pull request; его сначала смотрят.

## Ответственность по областям

| Область | Каталог |
| --- | --- |
| Движок захвата | `src/capture/` |
| Движки протокола и гипотез | `src/protocol/`, `src/hypothesis/` |
| Окно, проект, отчёт, презентация | `src/ui/`, `src/project/`, `src/report/`, `presentation/` |
| Общие контракты и схемы | `docs/CONTRACT.md`, `docs/schemas/` — менять по согласованию, никогда молча |
