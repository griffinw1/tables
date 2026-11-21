"""Schema-less protobuf (proto2 wire format) DECODER for Tock's API responses.

Read-only subset of resy-sniper/tock_sniper/proto.py. The encoders for lock and
unlock request bodies were deliberately left out.
"""

from __future__ import annotations


def _read_varint(buf: bytes, i: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        shift += 7
        if b < 0x80:
            return result, i


def decode(buf: bytes) -> list[tuple[int, int | bytes]]:
    """One level of (field, value) pairs. Raises ValueError if `buf` isn't a message."""
    out: list[tuple[int, int | bytes]] = []
    i = 0
    try:
        while i < len(buf):
            key, i = _read_varint(buf, i)
            num, wire = key >> 3, key & 7
            if num == 0:
                raise ValueError("field 0")
            if wire == 0:
                value, i = _read_varint(buf, i)
            elif wire == 1:
                value, i = int.from_bytes(buf[i:i + 8], "little"), i + 8
            elif wire == 5:
                value, i = int.from_bytes(buf[i:i + 4], "little"), i + 4
            elif wire == 2:
                n, i = _read_varint(buf, i)
                value, i = buf[i:i + n], i + n
                if i > len(buf):
                    raise ValueError("truncated")
            else:
                raise ValueError(f"wire type {wire}")
            out.append((num, value))
    except IndexError as exc:
        raise ValueError("truncated") from exc
    return out


def messages(buf: bytes, *path: int) -> list[bytes]:
    """All sub-messages at a field path, e.g. messages(cal, 1, 1, 60686, 1)."""
    cur = [buf]
    for num in path:
        cur = [v for m in cur for n, v in decode(m) if n == num and isinstance(v, bytes)]
    return cur


def first_fields(buf: bytes) -> dict[int, int | bytes]:
    f: dict[int, int | bytes] = {}
    for num, value in decode(buf):
        f.setdefault(num, value)
    return f
