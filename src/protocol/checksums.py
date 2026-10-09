"""Checksum algorithms used by the ``checksum`` field type.

These are the simple variants a researcher reaches for first when probing a
binary protocol: ``xor`` and ``sum`` folding, and CRC-8/CRC-16. The same
functions back the standalone parser export, so a generated parser checks a
checksum exactly the way the engine does.
"""

from __future__ import annotations

ALGORITHMS = ("xor", "sum", "crc8", "crc16")


def compute(algorithm: str, data: bytes) -> int:
    """Return the checksum of *data* under *algorithm*."""
    if algorithm == "xor":
        return _xor(data)
    if algorithm == "sum":
        return _sum(data)
    if algorithm == "crc8":
        return _crc8(data)
    if algorithm == "crc16":
        return _crc16(data)
    raise ValueError(f"unknown checksum algorithm {algorithm!r}")


def width_for(algorithm: str) -> int:
    """Number of bytes a checksum of *algorithm* occupies."""
    return 2 if algorithm == "crc16" else 1


def _xor(data: bytes) -> int:
    value = 0
    for byte in data:
        value ^= byte
    return value


def _sum(data: bytes) -> int:
    return sum(data) & 0xFF


def _crc8(data: bytes, polynomial: int = 0x07) -> int:
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ polynomial) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def _crc16(data: bytes, polynomial: int = 0x1021) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ polynomial) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc
