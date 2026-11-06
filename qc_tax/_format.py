"""
Money formatting and parsing without floating-point damage.

Two locales matter for Canadian invoices and both use a *different* decimal
separator, which is the classic source of "1,50" meaning 150 in one place and
1.50 in another.

>>> format_money("114.98")
'$114.98'
>>> format_money("114.98", locale="fr-CA")
'114,98 $'
>>> parse_money("1 234,56 $")
Decimal('1234.56')
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Union

__all__ = [
    "format_money",
    "format_money_cents",
    "parse_money",
    "to_cents",
    "from_cents",
]

_CENT = Decimal("0.01")


def _dec(value: Union[str, int, Decimal, float]) -> Decimal:
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, bool):
        raise TypeError("money must not be a bool")
    elif isinstance(value, int):
        d = Decimal(value)
    elif isinstance(value, float):
        d = Decimal(str(value))
    elif isinstance(value, str):
        s = value.strip().replace("\u00a0", "").replace(" ", "")
        s = s.replace("$", "").replace("CA", "").replace("CAD", "")
        s = s.replace(",", ".")
        try:
            d = Decimal(s)
        except InvalidOperation:
            raise ValueError(f"not a money value: {value!r}") from None
    else:
        raise TypeError(f"money must be str/int/Decimal/float, got {type(value).__name__}")
    if not d.is_finite():
        raise ValueError(f"not a finite money value: {value!r}")
    return d.quantize(_CENT, rounding=ROUND_HALF_UP)


def _group(int_part: str, sep: str) -> str:
    neg = int_part.startswith("-")
    digits = int_part.lstrip("-")
    out = []
    while len(digits) > 3:
        out.insert(0, digits[-3:])
        digits = digits[:-3]
    out.insert(0, digits)
    return ("-" if neg else "") + sep.join(out)


def format_money(
    value: Union[str, int, Decimal, float],
    *,
    locale: str = "en-CA",
    symbol: bool = True,
    thousands: bool = True,
) -> str:
    """
    Format a monetary amount for a Canadian invoice.

    ``en-CA`` → ``$1,234.56`` ; ``fr-CA`` → ``1 234,56 $`` (narrow no-break
    spaces as Québécois typography requires).
    """
    d = _dec(value)
    sign = "-" if d < 0 else ""
    d = abs(d)
    int_part, frac = f"{d:.2f}".split(".")

    if locale.lower().startswith("fr"):
        grp = "\u202f" if thousands else ""
        body = f"{sign}{_group(int_part, grp)},{frac}"
        return f"{body} $" if symbol else body

    grp = "," if thousands else ""
    body = f"{sign}{_group(int_part, grp)}.{frac}"
    return f"${body}" if symbol else body


def format_money_cents(cents: int) -> str:
    """Format an integer number of cents as dollars: ``11498`` → ``'$114.98'``."""
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise TypeError(f"cents must be int, got {type(cents).__name__}")
    return format_money(Decimal(cents) / 100)


def parse_money(text: str) -> Decimal:
    """
    Parse a money string from either Canadian locale into exact Decimals.

    Handles ``,``/``.`` decimal separators, narrow and regular spaces, currency
    symbols and the ``CAD`` prefix/suffix.
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be str, got {type(text).__name__}")
    s = text.strip().replace("\u00a0", "").replace("\u202f", "").replace(" ", "")
    s = s.replace("$", "").replace("CAD", "").replace("CA", "")
    if not s:
        raise ValueError("empty money string")

    has_dot, has_comma = "." in s, "," in s
    if has_dot and has_comma:
        # whichever appears LAST is the decimal separator
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_comma:
        # "1,234" is ambiguous; "1,50" is clearly a decimal comma.
        after = s.rsplit(",", 1)[1]
        s = s.replace(",", ".") if len(after) <= 2 else s.replace(",", "")

    try:
        d = Decimal(s)
    except InvalidOperation:
        raise ValueError(f"not a money value: {text!r}") from None
    if not d.is_finite():
        raise ValueError(f"not a money value: {text!r}")
    return d.quantize(_CENT, rounding=ROUND_HALF_UP)


def to_cents(value: Union[str, int, Decimal, float]) -> int:
    """Convert a dollar amount to integer cents (ROUND_HALF_UP)."""
    return int(_dec(value) * 100)


def from_cents(cents: int) -> Decimal:
    """Convert integer cents to an exact Decimal of dollars."""
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise TypeError(f"cents must be int, got {type(cents).__name__}")
    return (Decimal(cents) / 100).quantize(_CENT)
