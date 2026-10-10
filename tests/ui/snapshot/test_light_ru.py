"""Snapshot coverage: light theme, Russian interface.

Five images, one per supported window size. The window state is pinned by
``tests.ui.support``; the reference capture and rule are the ones the product
ships.
"""

from __future__ import annotations


from tests.ui.snapshot._diff import assert_snapshot
from tests.ui.support import grab, set_state, snapshot_name

THEME = "light"
LANGUAGE = "ru"


def test_snapshot(window, app, resolution):
    set_state(window, app, language=LANGUAGE, theme_mode=THEME, resolution=resolution, zoom=100)
    assert_snapshot(snapshot_name(THEME, LANGUAGE, resolution), grab(window))
