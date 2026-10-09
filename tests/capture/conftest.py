"""Shared helpers for the capture engine tests."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
SCHEMAS = Path(__file__).resolve().parent.parent.parent / "docs" / "schemas"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


def fixture(name: str) -> Path:
    return FIXTURES / name


def defect(name: str) -> Path:
    return FIXTURES / "defects" / name
