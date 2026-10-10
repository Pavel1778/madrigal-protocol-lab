# Установка

Пошаговая установка каждым из форматов поставки. Установка из исходников — в
[README](../README.md); сборка артефактов из дерева — в [BINARY.md](BINARY.md);
готовые файлы — в релизе
[v1.0.0](https://github.com/Pavel1778/madrigal-protocol-lab/releases/tag/v1.0.0).

Требуется Linux x86-64 (glibc не старше той, на которой собран бинарник). Для
графического окна — X или Wayland; для запуска без экрана задайте
`QT_QPA_PLATFORM=offscreen`.

Общая проверка для бинарных форматов — команда печатает справку окна:

```
madrigal-lab --help
```

```
usage: src.ui.main_window [-h] [--capture CAPTURE] [--rule RULE]
```

## AppImage

Один файл, установка не требуется.

```
chmod +x protocol-lab-x86_64.AppImage
./protocol-lab-x86_64.AppImage
```

Проверка: `./protocol-lab-x86_64.AppImage --help`. Там, где недоступен FUSE
(например, в контейнере), распакуйте и запустите лаунчер:

```
./protocol-lab-x86_64.AppImage --appimage-extract
./squashfs-root/AppRun
```

## Пакет `.deb`

```
sudo dpkg -i madrigal-protocol-lab_1.0.0_amd64.deb
madrigal-lab
```

Пакет кладёт исполняемый файл в `/usr/bin/madrigal-lab`, значок и ярлык в
`/usr/share`, а документацию, шрифты и корпус в
`/usr/share/madrigal-protocol-lab`.

Проверка без установки в систему:

```
dpkg-deb -I madrigal-protocol-lab_1.0.0_amd64.deb
dpkg-deb -x madrigal-protocol-lab_1.0.0_amd64.deb /tmp/deb-test
/tmp/deb-test/usr/bin/madrigal-lab --help
```

Удаление: `sudo dpkg -r madrigal-protocol-lab`.

## Самораспаковывающийся `.run`

```
chmod +x madrigal-lab.run
./madrigal-lab.run
```

По умолчанию ставит в `~/.local`; другой префикс задаётся переменной `PREFIX`:

```
PREFIX=/usr/local ./madrigal-lab.run
```

Проверка без установки (только распаковка):

```
./madrigal-lab.run --target /tmp/run-extract
/tmp/run-extract/madrigal-lab --help
```

Удаление: `rm -f ~/.local/bin/madrigal-lab` и ярлык со значками в
`~/.local/share`.

## Однофайловый бинарник

```
chmod +x madrigal-lab
./madrigal-lab --capture normalized.json --rule rule.json
```

Портативный файл без установки; без аргументов открывает пустое окно. Подробности
и проверенные сценарии — в [BINARY.md](BINARY.md).

## Docker-образ

```
docker build -t madrigal-protocol-lab .
docker run --rm madrigal-protocol-lab pytest tests/ -q
```

Образ содержит исходники, тесты, корпус, зависимости и библиотеки Qt, поэтому
окно запускается без подготовки хоста. `QT_QPA_PLATFORM=offscreen` задан в
образе, так что команда по умолчанию (`python -m src.ui.main_window`) стартует
окно без экрана:

```
docker run --rm madrigal-protocol-lab python -m src.ui.main_window --help
```

Видимому окну нужен сокет дисплея:

```
docker run --rm -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix madrigal-protocol-lab
```

Готовый образ переносится одним файлом:

```
docker save madrigal-protocol-lab | gzip > madrigal-protocol-lab-docker.tar.gz
docker load < madrigal-protocol-lab-docker.tar.gz
```

## Python-колесо

```
python -m venv venv
venv/bin/pip install madrigal_protocol_lab-1.0.0-py3-none-any.whl
venv/bin/madrigal-lab --help
```

Колесо ставит пакет и его зависимости (PySide6, dpkt, PyYAML) и консольную
команду `madrigal-lab`, но не тянет тестовый набор; тесты запускаются из дерева
исходников. Требуется Python 3.12+.

## Исходники

```
python -m venv venv
venv/bin/pip install -e ".[dev]"
venv/bin/madrigal-lab
```

Из дерева доступны и тесты: `venv/bin/pytest tests/ -q`.
