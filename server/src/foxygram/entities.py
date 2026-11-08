"""Identifiers found with plain code: exact, free, and never sent anywhere."""
from __future__ import annotations

import re
from dataclasses import dataclass

STRONG_TYPES = {"vin", "container"}

_VIN = re.compile(r"(?<![A-Za-z0-9])[A-HJ-NPR-Za-hj-npr-z0-9]{17}(?![A-Za-z0-9])")
_CONTAINER = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{3}[UJZuJz])[\s-]?(\d{6})[\s-]?(\d)(?![A-Za-z0-9])")
_PHONE = re.compile(r"(?<![\d+])(\+?\d[\d\s()\-]{8,16}\d)(?!\d)")
_INVOICE = re.compile(
    r"(?:инвойс\w*|invoice|сч[её]т\w*|CMR|ЦМР)\s*(?:№|#|N|no\.?)?\s*([A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9/\-]{2,24})",
    re.IGNORECASE,
)

_CONTAINER_VALUES = {
    letter: value
    for letter, value in zip(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        (10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 34, 35, 36, 37, 38),
    )
}


@dataclass(frozen=True, order=True)
class Entity:
    type: str
    value: str


def container_is_valid(code: str) -> bool:
    """ISO 6346 check digit, which keeps random 11-character strings out."""
    if len(code) != 11:
        return False
    total = 0
    for position, char in enumerate(code[:10]):
        value = _CONTAINER_VALUES[char] if char.isalpha() else int(char)
        total += value * (1 << position)
    return (total % 11) % 10 == int(code[10])


def _looks_like_vin(token: str) -> bool:
    letters = sum(c.isalpha() for c in token)
    digits = sum(c.isdigit() for c in token)
    return letters >= 2 and digits >= 3


def extract(text: str) -> list[Entity]:
    if not text:
        return []
    found: set[Entity] = set()
    for match in _VIN.finditer(text):
        token = match.group(0).upper()
        if _looks_like_vin(token):
            found.add(Entity("vin", token))
    for match in _CONTAINER.finditer(text):
        code = (match.group(1) + match.group(2) + match.group(3)).upper()
        if container_is_valid(code):
            found.add(Entity("container", code))
    for match in _PHONE.finditer(text):
        digits = re.sub(r"\D", "", match.group(1))
        if 10 <= len(digits) <= 15:
            found.add(Entity("phone", digits))
    for match in _INVOICE.finditer(text):
        value = match.group(1).upper()
        if any(c.isdigit() for c in value):
            found.add(Entity("invoice", value))
    return sorted(found)
