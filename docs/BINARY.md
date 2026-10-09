# Binary and package

A single-file Linux binary and a `.deb` built from it, for a machine without a
Python setup.

## Build

```
pip install pyinstaller
scripts/build_linux_binary.sh     # -> dist/madrigal-lab
scripts/build_deb.sh              # -> dist/madrigal-protocol-lab_<version>_amd64.deb
```

`build_deb.sh` packages the binary from `build_linux_binary.sh`; run them in
that order. Both need `dist/madrigal-lab` to exist.

The binary bundles the interpreter, PySide6, the fonts, the docs and the
corpus, so it is one file with no install. Build on the oldest glibc you intend
to support: the result does not run on an older one.

## Size

| Artefact | Size |
| --- | --- |
| `dist/madrigal-lab` | about 71 MB |
| `dist/madrigal-protocol-lab_0.1.0_amd64.deb` | about 70 MB |

Most of the size is Qt and the bundled CPython. The binary is not compressed.

## Run

```
./dist/madrigal-lab --capture <normalized.json> --rule <rule.json>
```

Without arguments it opens an empty window. On a machine with no display, set
`QT_QPA_PLATFORM=offscreen`.

The `.deb` installs the executable at `/usr/bin/madrigal-lab`, the icon and
desktop entry under `/usr/share`, and the docs, fonts and corpus under
`/usr/share/madrigal-protocol-lab`:

```
sudo dpkg -i dist/madrigal-protocol-lab_0.1.0_amd64.deb
madrigal-lab
```

## What was verified

- The binary prints the usage of the window entry point and starts the window
  headless with a capture and a rule (`QT_QPA_PLATFORM=offscreen`), where it
  runs until the timeout.
- The `.deb` is built with `dpkg-deb`; extracting it and running
  `usr/bin/madrigal-lab --help` prints the usage.
- The package was built and checked on the development host, not installed
  system-wide, and not run on a second machine.

## Not covered

- A real display was not available, so the window was exercised headless only.
- The binary was not tested on Ubuntu 22.04 or another glibc as a packaged
  artefact; the source suite is checked in those environments (see
  `docs/PORTABILITY.md`), not this binary.
- The desktop entry assumes `Icon=madrigal-lab` resolves through the hicolor
  theme; the icon was not checked in a running desktop session.
