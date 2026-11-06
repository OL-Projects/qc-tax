"""
qc-tax — exact-to-the-cent Canadian sales tax math.

Why this package exists
-----------------------
Getting Québec tax arithmetic wrong is easy and expensive:

* **QST is NOT compounded.** Both GST (5%) and QST (9.975%) are calculated on
  the *pre-tax* selling price. Calculating QST on the GST-inclusive amount
  over-charges the customer on every invoice.
* **Each tax rounds to the cent independently.** On $100.00 the correct QST is
  $9.98 (9.9750 → 9.98), not $9.97 and not 8.75 + something.
* **`float` loses cents.** `round(0.09975 * 100, 2)` is fine, but
  `round(2.675, 2) == 2.67` in float — a classic off-by-a-cent bug on money.
* **Extracting tax from a tax-included price needs the combined divisor**
  ($114.975 for Québec), and the two components must *re-sum to the total*.

This library does all of that in integer cents with banker's-free, tax-authority
style **ROUND_HALF_UP** rounding, and it exposes every step so you can explain
the number to a client or an auditor.

Scope
-----
2026 Canadian sales tax: GST, HST (all participating provinces), QST (Québec),
PST (BC, SK, MB). Not a filing tool, not tax advice.

Example
-------
>>> from qc_tax import calculate
>>> r = calculate("100.00")
>>> str(r.gst), str(r.qst), str(r.total)
('5.00', '9.98', '114.98')

>>> from qc_tax import extract
>>> str(extract("114.98").qst)
'9.98'
"""

from ._core import (
    Alberta,
    BackTaxed,
    BritishColumbia,
    Manitoba,
    NewBrunswick,
    NewfoundlandAndLabrador,
    NovaScotia,
    Ontario,
    PrinceEdwardIsland,
    Provinces,
    Quebec,
    Saskatchewan,
    Territory,
    CanadianTaxError,
    InvalidRate,
    InvalidRounding,
    NegativeAmount,
    TaxResult,
    by_code,
    calculate,
    extract,
    provinces,
    rate_for,
)
from ._format import (
    format_money,
    format_money_cents,
    from_cents,
    parse_money,
    to_cents,
)
from ._sin import (
    InvalidSIN,
    format_sin,
    is_valid_sin,
    normalize_sin,
    validate_sin,
)

__version__ = "1.0.0"

__all__ = [
    # calculation
    "calculate",
    "extract",
    "rate_for",
    "provinces",
    "by_code",
    "TaxResult",
    # formatting
    "format_money",
    "format_money_cents",
    "parse_money",
    "to_cents",
    "from_cents",
    # SIN helpers
    "validate_sin",
    "is_valid_sin",
    "normalize_sin",
    "format_sin",
    "InvalidSIN",
    # jurisdiction rates
    "Alberta",
    "BritishColumbia",
    "Manitoba",
    "NewBrunswick",
    "NewfoundlandAndLabrador",
    "NovaScotia",
    "Ontario",
    "PrinceEdwardIsland",
    "Quebec",
    "Saskatchewan",
    "Territory",
    "Provinces",
    # errors
    "CanadianTaxError",
    "NegativeAmount",
    "InvalidRate",
    "InvalidRounding",
    "BackTaxed",
    # meta
    "__version__",
]
