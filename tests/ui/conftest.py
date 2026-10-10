"""Shared isolation for the window tests.

The window, the theme and the language each persist their choice in
``QSettings`` under the ``madrigal`` organisation, and ``system`` language
resolves to the desktop locale. A developer who once chose Russian in the
running application therefore has ``interface/language=ru`` on disk, and on a
Russian desktop the ``system`` preference also selects the Russian catalogue.
Either way the English-string assertions in these tests would fail on that
machine while passing on a clean CI runner.

Qt resolves the settings path from ``XDG_CONFIG_HOME`` on the first
``QSettings`` use and caches it, so redirecting that variable *before* any
settings object is created sends every store — the window's, the theme's and
the language's, however they captured the organisation constants — to a
throwaway directory. The system locale is pinned for the same reason: it is
what ``system`` resolves against.

Both are set at import time of this module, which pytest loads before the test
modules, so the redirection is in place before the first ``QSettings`` is built.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile

# A throwaway settings root: nothing here is read back by a later run, and the
# developer's real preferences under ~/.config are never touched.
_CONFIG_ROOT = tempfile.mkdtemp(prefix="madrigal-test-config-")
atexit.register(shutil.rmtree, _CONFIG_ROOT, True)
os.environ["XDG_CONFIG_HOME"] = _CONFIG_ROOT

# Pin the locale so the "system" preference resolves to English regardless of
# the developer's desktop language. C.UTF-8 is present on every target.
os.environ["LANG"] = "C.UTF-8"
os.environ["LC_ALL"] = "C.UTF-8"
