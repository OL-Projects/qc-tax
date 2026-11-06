"""
Canadian Social Insurance Number (SIN) validation and formatting.

This module performs the **offline Luhn check only**. It does not contact
Employment and Social Development Canada (ESDC), the Social Insurance Registry
or any other service, and it cannot — ESDC's SIN verification ("SIN confirmation")
is a paid, employer-only service. A SIN that passes here is *well-formed*, not
*assigned*: 000 000 001 satisfies Luhn but belongs to nobody.

Validity rules for a Canadian SIN
---------------------------------
* exactly nine digits after stripping separators;
* the number is not ``000 000 000`` (never issued, though it passes Luhn);
* the check digit (position 9) satisfies Luhn.

Note that a *leading zero is legal*: ESDC issues SINs starting with 0, and the
Canada Revenue Agency's own published example is ``046 454 286``. Rejecting
leading zeros (a common bug in SIN validators) would reject real SINs.

Privacy note
------------
A SIN is sensitive personal information. Nothing here logs, stores or transmits
one. ``normalize_sin`` is provided so you can strip separators before hashing
or before writing a SIN to a system that stores it encrypted.

>>> is_valid_sin("046 454 286")
True
>>> format_sin("046454286")
'046 454 286'
"""

from __future__ import annotations

import re
from typing import Union

__all__ = [
    "InvalidSIN",
    "is_valid_sin",
    "validate_sin",
    "normalize_sin",
    "format_sin",
]

_SEP = re.compile(r"[\s\-_.·]")
_DIGITS = re.compile(r"^\d{9}$")


class InvalidSIN(ValueError):
    """A supplied value is not a well-formed Canadian SIN."""


def normalize_sin(value: Union[str, int]) -> str:
    """
    Strip spaces, hyphens, dots and middle dots, and return the bare 9 digits.

    Raises :class:`InvalidSIN` if the result is not exactly nine digits.
    Leading zeros are preserved (they are part of the number).
    """
    if isinstance(value, bool):
        raise InvalidSIN("a SIN cannot be a bool")
    if isinstance(value, int):
        # an int SIN loses its leading zeros, so accept it but say so clearly
        s = str(value)
        if len(s) != 9:
            raise InvalidSIN(
                f"SIN {value} has {len(s)} digits, expected 9 "
                "(pass it as a string to preserve a leading zero)"
            )
        return s
    if not isinstance(value, str):
        raise InvalidSIN(f"a SIN must be str or int, got {type(value).__name__}")

    s = _SEP.sub("", value.strip())
    if not s:
        raise InvalidSIN("SIN is empty")
    if not _DIGITS.match(s):
        raise InvalidSIN(f"a SIN must be exactly 9 digits, got {len(s)} character(s)")
    return s


def _luhn_ok(digits: str) -> bool:
    total = 0
    # Double every second digit counting from the right (check digit is pos 9,
    # so positions 8, 6, 4, 2 get doubled).
    for i, ch in enumerate(reversed(digits)):
        d = ord(ch) - 48
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def is_valid_sin(value: Union[str, int]) -> bool:
    """
    True if ``value`` is a well-formed Canadian SIN (offline Luhn only).

    Never raises for a bad value — that is the point of a predicate.

    >>> is_valid_sin("046 454 286")
    True
    >>> is_valid_sin("046 454 287")
    False
    >>> is_valid_sin("000 000 000")
    False
    """
    try:
        s = normalize_sin(value)
    except InvalidSIN:
        return False
    if s == "000000000":
        # The all-zero number is never issued, though it passes Luhn.
        return False
    return _luhn_ok(s)


def validate_sin(value: Union[str, int]) -> str:
    """
    Return the normalized SIN if it is valid, otherwise raise :class:`InvalidSIN`
    with a message that says *why* it failed.
    """
    s = normalize_sin(value)
    if s == "000000000":
        raise InvalidSIN("000 000 000 is never issued as a SIN")
    if not _luhn_ok(s):
        raise InvalidSIN("SIN fails the Luhn check digit test")
    return s


def format_sin(value: Union[str, int], style: str = "space") -> str:
    """
    Format a SIN for display.

    ``style`` is ``"space"`` (``046 454 286``), ``"dash"`` (``046-454-286``) or
    ``"plain"`` (``046454286``).
    """
    s = validate_sin(value)
    if style == "plain":
        return s
    if style == "dash":
        return f"{s[0:3]}-{s[3:6]}-{s[6:9]}"
    if style == "space":
        return f"{s[0:3]} {s[3:6]} {s[6:9]}"
    raise ValueError(f"style must be 'space', 'dash' or 'plain', got {style!r}")
