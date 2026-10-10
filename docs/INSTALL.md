# Установка

Краткие шаги для каждого формата поставки. Установка из исходников — в
[README](../README.md); сборка артефактов — в [BINARY.md](BINARY.md).

Требуется Linux x86-64. Для графического окна — X или Wayland; для запуска без
экрана задайте `QT_QPA_PLATFORM=offscreen`.

## Docker-образ

```
docker build -t protocol-lab .
docker run --rm protocol-lab pytest tests/ -q
```

Окно требует проброса сокета дисплея:

```
docker run --rm -e QT_QPA_PLATFORM=offscreen \
    -v "$PWD:/out" protocol-lab \
    python -m src.capture.cli --pcap /out/capture.pcapng --out /out/normalized.json
```

## Пакет `.deb`

```
sudo dpkg -i madrigal-protocol-lab_1.0.0_amd64.deb
madrigal-lab
```

Пакет кладёт исполняемый файл в `/usr/bin/madrigal-lab`, значок и ярлык в
`/usr/share`, а документацию, шрифты и корпус в
`/usr/share/madrigal-protocol-lab`.

## AppImage

```
chmod +x protocol-lab-x86_64.AppImage
./protocol-lab-x86_64.AppImage
```

Один файл, установка не требуется. Там, где недоступен FUSE, распакуйте и
запустите вручную:

```
./protocol-lab-x86_64.AppImage --appimage-extract
./squashfs-root/AppRun
```

## Самораспаковывающийся `.run`

```
chmod +x madrigal-lab.run
./madrigal-lab.run
```

По умолчанию ставит в `~/.local`; другой префикс задаётся переменной `PREFIX`:

```
PREFIX=/usr/local ./madrigal-lab.run
```

## Python-колесо

```
pip install madrigal_protocol_lab-1.0.0-py3-none-any.whl
python -m src.capture.cli --pcap capture.pcapng --out normalized.json
```

Колесо ставит пакет и его зависимости (PySide6, dpkt, PyYAML), но не тянет
тестовый набор; тесты запускаются из дерева исходников.

## Однофайловый бинарник

```
./madrigal-lab --capture normalized.json --rule rule.json
```

Подробности и проверенные сценарии — в [BINARY.md](BINARY.md).
