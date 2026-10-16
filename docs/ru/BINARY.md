# Бинарники и пакеты

Английский оригинал: [BINARY.md](../BINARY.md).

Два однофайловых артефакта Linux, собранные из одного замороженного бинарника, —
голый исполняемый файл, `.deb`, AppImage и самораспаковывающийся `.run`, — плюс
Python-колесо для машины, где уже есть Python. Всё для машины без выгрузки
исходников.

## Сборка

```
pip install pyinstaller
pip install build            # для колеса
scripts/build_linux_binary.sh     # -> dist/madrigal-lab
scripts/build_deb.sh              # -> dist/madrigal-protocol-lab_<version>_amd64.deb
scripts/build_appimage.sh         # -> dist/protocol-lab-x86_64.AppImage
scripts/build_run.sh              # -> dist/madrigal-lab.run
python -m build --wheel           # -> dist/madrigal_protocol_lab-<version>-py3-none-any.whl
```

`build_deb.sh`, `build_appimage.sh` и `build_run.sh` упаковывают бинарник из
`build_linux_binary.sh`; сначала запустите его. `build_appimage.sh` скачивает
`appimagetool` в `.scratch/` и запускает его распакованным, поэтому FUSE во время
сборки не нужен.

Бинарник несёт внутри интерпретатор, PySide6, шрифты, документацию и корпус,
поэтому это один файл без установки. Собирайте на самой старой glibc, которую
намерены поддерживать: результат не запустится на более старой.

## Размер

| Артефакт | Размер |
| --- | --- |
| `dist/madrigal-lab` | около 71 МБ |
| `dist/madrigal-protocol-lab_1.0.0_amd64.deb` | около 70 МБ |
| `dist/protocol-lab-x86_64.AppImage` | около 71 МБ |
| `dist/madrigal-lab.run` | около 71 МБ |
| `dist/madrigal_protocol_lab-1.0.0-py3-none-any.whl` | около 175 КБ |
| `dist/madrigal-protocol-lab-docker.tar.gz` | около 540 МБ (сжатый образ) |

Большая часть размера — Qt и встроенный CPython. Бинарник не сжат; AppImage и
`.run` несут тот же бинарник в SquashFS и в gzip-архиве соответственно.

## Запуск

```
./dist/madrigal-lab --capture <normalized.json> --rule <rule.json>
```

Без аргументов открывает пустое окно. На машине без дисплея задайте
`QT_QPA_PLATFORM=offscreen`.

`.deb` ставит исполняемый файл в `/usr/bin/madrigal-lab`, значок и ярлык в
`/usr/share`, а документацию, шрифты и корпус в
`/usr/share/madrigal-protocol-lab`:

```
sudo dpkg -i dist/madrigal-protocol-lab_1.0.0_amd64.deb
madrigal-lab
```

AppImage запускается из любого каталога без установки. Там, где нет FUSE,
распакуйте и запустите лаунчер:

```
chmod +x dist/protocol-lab-x86_64.AppImage
./dist/protocol-lab-x86_64.AppImage --appimage-extract
./squashfs-root/AppRun
```

`.run` ставит бинарник, ярлык и значки в `~/.local` (или `$PREFIX`):

```
chmod +x dist/madrigal-lab.run
PREFIX=/tmp/prefix ./dist/madrigal-lab.run
```

Колесо ставит пакет и его зависимости:

```
pip install dist/madrigal_protocol_lab-1.0.0-py3-none-any.whl
```

## Docker

Образ несёт исходники, тесты, корпус и закреплённые зависимости, плюс библиотеки
среды исполнения Qt, которые нужны окну. Он запускает набор или окно без
подготовки хоста:

```
docker build -t madrigal-protocol-lab .
docker run --rm madrigal-protocol-lab pytest tests/ -q
docker run --rm madrigal-protocol-lab python -m src.ui.main_window --help
```

`QT_QPA_PLATFORM=offscreen` задан в образе, поэтому `CMD` по умолчанию
(`python -m src.ui.main_window`) стартует окно без экрана. Видимому окну
дополнительно нужен сокет X:

```
docker run --rm -e DISPLAY \
    -v /tmp/.X11-unix:/tmp/.X11-unix madrigal-protocol-lab
```

Сохранить и загрузить собранный образ одним файлом:

```
docker save madrigal-protocol-lab | gzip > dist/madrigal-protocol-lab-docker.tar.gz
docker load < dist/madrigal-protocol-lab-docker.tar.gz
```

Сжатый образ велик (около 540 МБ): это Debian slim плюс CPython, PySide6 и
библиотеки Qt, а не уменьшение бинарника на 71 МБ, поэтому это путь сборки из
`Dockerfile`, а не путь скачивания.

## Что проверено

- Бинарник печатает справку точки входа окна и запускает окно без экрана с
  захватом и правилом (`QT_QPA_PLATFORM=offscreen`), где работает до тайм-аута.
- `.deb` собран через `dpkg-deb`; его распаковка и запуск
  `usr/bin/madrigal-lab --help` печатает справку.
- AppImage собран через `appimagetool`, распакован через
  `--appimage-extract`, и `squashfs-root/AppRun --help` печатает справку.
- `.run` собран через `makeself`, установлен во временный `PREFIX`, и
  установленный `bin/madrigal-lab --help` печатает справку; ярлык и все
  отрисованные размеры значков попадают под префикс.
- Колесо собирается `python -m build` и сообщает версию `1.0.0`. Свежее
  виртуальное окружение, установленное из колеса, разрешает `madrigal-lab` как
  консольный скрипт и печатает справку окна.
- Образ Docker собирается `docker build`; `docker run --rm ... python -m
  src.ui.main_window --help` печатает справку, а `CMD` по умолчанию стартует окно
  без экрана (offscreen). Библиотеки среды исполнения Qt установлены в образе,
  поэтому окно импортируется без хостового `libglib`. Образ выгружается через
  `docker save | gzip`.
- Приложение регистрирует id своего ярлыка (`madrigal-protocol-lab`) при запуске,
  поэтому док разрешает значок окна из установленного ярлыка, а не только из
  значка заголовка.
- Пакет собран и проверен на хосте разработки, не установлен в систему и не
  запущен на второй машине.

## Что не покрыто

- Настоящего дисплея не было, поэтому окно упражнялось только без экрана.
- Бинарник не тестировался на Ubuntu 22.04 или другой glibc как упакованный
  артефакт; исходный набор проверяется в тех окружениях (см.
  `docs/PORTABILITY.md`), а не этот бинарник.
- Ярлык предполагает, что `Icon=madrigal-lab` разрешается через тему hicolor;
  значок не проверялся в работающей сессии рабочего стола.
