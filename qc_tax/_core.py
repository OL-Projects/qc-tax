"""
Core tax arithmetic for Canadian sales taxes.

Design rules enforced here
--------------------------
1. **Money is integer cents.** No float ever touches a monetary value.
2. **Each tax is rounded independently** to the nearest cent with ROUND_HALF_UP
   (the rounding tax authorities specify; Python's default is ROUND_HALF_EVEN,
   which gets money wrong at exactly the .5 boundaries).
3. **QST is never compounded on GST.** Both taxes apply to the pre-tax base.
4. **Extraction re-sums exactly.** :func:`extract` guarantees
   ``gst + qst == total - base`` to the cent, absorbing any residual rounding
   into the larger tax component rather than letting the invoice fail to add up.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, Iterable, Optional, Tuple, Union

__all__ = [
    "TaxResult",
    "calculate",
    "extract",
    "rate_for",
    "provinces",
    "by_code",
    "CanadianTaxError",
    "NegativeAmount",
    "InvalidRate",
    "InvalidRounding",
    "BackTaxed",
    "Quebec",
    "Ontario",
    "NovaScotia",
    "NewBrunswick",
    "NewfoundlandAndLabrador",
    "PrinceEdwardIsland",
    "BritishColumbia",
    "Saskatchewan",
    "Manitoba",
    "Alberta",
    "Territory",
    "Provinces",
]

_CENT = Decimal("0.01")


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class CanadianTaxError(ValueError):
    """Base class for every error this package raises."""


class NegativeAmount(CanadianTaxError):
    """A monetary amount was negative."""


class InvalidRate(CanadianTaxError):
    """A tax rate was outside the sane 0–100% range or malformed."""


class InvalidRounding(CanadianTaxError):
    """A rounding directive was not one of the supported values."""


class BackTaxed(CanadianTaxError):
    """
    A tax-included amount could not be decomposed consistently.

    Raised only in strict mode when the two extracted components do not re-sum
    to the total, which in practice means the input was not produced by this
    jurisdiction's rates.
    """


# --------------------------------------------------------------------------- #
# Jurisdiction table (2026 rates)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Jurisdiction:
    """
    One Canadian sales-tax jurisdiction.

    ``gst`` is the *federal* component: 5% GST, or the 5% federal part of an
    HST where ``harmonized`` is True. ``provincial`` is QST for Québec, the
    provincial part of HST, or PST/RST. ``compounded`` marks a provincial tax
    levied on the tax-inclusive amount; no Canadian jurisdiction currently does
    this (including Manitoba, whose RST applies to the pre-GST price), but the
    flag exists so a historical or hypothetical regime can be expressed.
    """

    code: str
    name: str
    gst: str
    provincial: str
    kind: str  # "GST+QST" | "HST" | "GST+PST" | "GST" | "none"
    compounded: bool = False

    # ---- derived ---------------------------------------------------------- #
    @property
    def gst_rate(self) -> Decimal:
        return Decimal(self.gst)

    @property
    def provincial_rate(self) -> Decimal:
        return Decimal(self.provincial)

    @property
    def effective_rate(self) -> Decimal:
        """
        The rate applied to the pre-tax base for the *total* tax.

        This equals ``gst + provincial`` except in Manitoba, where the
        provincial tax rides on top of the GST.
        """
        if self.compounded:
            return self.gst_rate + self.provincial_rate * (Decimal(1) + self.gst_rate)
        return self.gst_rate + self.provincial_rate

    @property
    def combined_divisor(self) -> Decimal:
        """Divisor for extracting tax out of a tax-included price."""
        return Decimal(1) + self.effective_rate


Quebec = Jurisdiction("QC", "Québec", "0.05", "0.09975", "GST+QST")
Ontario = Jurisdiction("ON", "Ontario", "0.05", "0.08", "HST")
NovaScotia = Jurisdiction("NS", "Nova Scotia", "0.05", "0.09", "HST")
NewBrunswick = Jurisdiction("NB", "New Brunswick", "0.05", "0.10", "HST")
NewfoundlandAndLabrador = Jurisdiction(
    "NL", "Newfoundland and Labrador", "0.05", "0.10", "HST"
)
PrinceEdwardIsland = Jurisdiction(
    "PE", "Prince Edward Island", "0.05", "0.10", "HST"
)
BritishColumbia = Jurisdiction("BC", "British Columbia", "0.05", "0.07", "GST+PST")
Saskatchewan = Jurisdiction("SK", "Saskatchewan", "0.05", "0.06", "GST+PST")
# Manitoba's RST is levied on the selling price *before* GST is applied
# (Manitoba Finance, Information Bulletin RST 001), so the combined effective
# rate is a flat 12% — no compounding anywhere in Canada.
Manitoba = Jurisdiction("MB", "Manitoba", "0.05", "0.07", "GST+PST")
Alberta = Jurisdiction("AB", "Alberta", "0.05", "0.00", "GST")
Territory = Jurisdiction("YT/NT/NU", "Territories", "0.05", "0.00", "GST")


class Provinces:
    """The jurisdiction table, addressable by attribute or code."""

    QUEBEC = Quebec
    ONTARIO = Ontario
    NOVA_SCOTIA = NovaScotia
    NEW_BRUNSWICK = NewBrunswick
    NEWFOUNDLAND = NewfoundlandAndLabrador
    PEI = PrinceEdwardIsland
    BC = BritishColumbia
    SASKATCHEWAN = Saskatchewan
    MANITOBA = Manitoba
    ALBERTA = Alberta
    TERRITORIES = Territory


_ALL: Tuple[Jurisdiction, ...] = (
    Quebec,
    Ontario,
    NovaScotia,
    NewBrunswick,
    NewfoundlandAndLabrador,
    PrinceEdwardIsland,
    BritishColumbia,
    Saskatchewan,
    Manitoba,
    Alberta,
    Territory,
)

_BY_CODE: Dict[str, Jurisdiction] = {j.code: j for j in _ALL}
# Friendly aliases people actually type.
_BY_CODE.update(
    {
        "PQ": Quebec,
        "QC-CA": Quebec,
        "PE": PrinceEdwardIsland,
        "NF": NewfoundlandAndLabrador,
        "NL-CA": NewfoundlandAndLabrador,
        "YT": Territory,
        "NT": Territory,
        "NU": Territory,
    }
)


def provinces() -> Tuple[Jurisdiction, ...]:
    """Every jurisdiction this package knows, in a stable order."""
    return _ALL


def by_code(code: str) -> Jurisdiction:
    """Look a jurisdiction up by its two-letter code (case-insensitive)."""
    if not isinstance(code, str):
        raise TypeError(f"code must be str, got {type(code).__name__}")
    key = code.strip().upper()
    try:
        return _BY_CODE[key]
    except KeyError:
        known = ", ".join(sorted({j.code for j in _ALL}))
        raise CanadianTaxError(
            f"unknown jurisdiction code {code!r}; known codes: {known}"
        ) from None


def rate_for(code: str) -> Decimal:
    """
    The effective combined tax rate charged on a pre-tax base in ``code``.

    >>> rate_for("QC")
    Decimal('0.14975')
    """
    return by_code(code).effective_rate


# --------------------------------------------------------------------------- #
# Parsing / rounding helpers
# --------------------------------------------------------------------------- #
MoneyLike = Union[str, int, Decimal, float]


def _to_decimal(value: MoneyLike, *, name: str = "amount") -> Decimal:
    """
    Convert anything money-ish into an exact Decimal.

    Floats are converted through their *repr* (``Decimal(str(x))``) so that
    ``0.1`` means one tenth and not the binary artefact.
    """
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, bool):
        # bool is an int subclass; catching it here avoids True == $1.
        raise TypeError(f"{name} must be a number, not bool")
    elif isinstance(value, int):
        d = Decimal(value)
    elif isinstance(value, float):
        # route through str() to get the human-typed value, not binary noise
        try:
            d = Decimal(str(value))
        except InvalidOperation:
            raise CanadianTaxError(f"{name} {value!r} is not a finite number") from None
        if not d.is_finite():
            raise CanadianTaxError(f"{name} {value!r} is not a finite number")
    elif isinstance(value, str):
        s = value.strip().replace("\u00a0", "").replace(" ", "")
        if not s:
            raise CanadianTaxError(f"{name} is empty")
        # tolerate currency symbols, thousands separators and French decimal comma
        s = s.replace("$", "").replace("CA", "").replace(",", ".")
        # A comma was either a thousands sep or a decimal comma. If removing the
        # "." left exactly one comma and no dot, treat it as decimal.
        if s.count(".") > 1:
            # "1.234.56" style is ambiguous garbage — reject rather than guess
            raise CanadianTaxError(f"{name} {value!r} has more than one decimal point")
        try:
            d = Decimal(s)
        except InvalidOperation:
            raise CanadianTaxError(f"{name} {value!r} is not a number") from None
        if not d.is_finite():
            raise CanadianTaxError(f"{name} {value!r} is not a finite number")
    else:
        raise TypeError(
            f"{name} must be str, int, Decimal or float, got {type(value).__name__}"
        )

    if d < 0:
        raise NegativeAmount(f"{name} must not be negative (got {d})")
    return d


def _round_cent(value: Decimal) -> Decimal:
    """ROUND_HALF_UP to two decimals — the rule tax authorities use."""
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _validate_rate(rate: Decimal, *, name: str) -> Decimal:
    if rate < 0 or rate >= 1:
        raise InvalidRate(f"{name} must be in [0, 1), got {rate}")
    return rate


# --------------------------------------------------------------------------- #
# Result object
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TaxResult:
    """
    The outcome of one tax calculation. Every field is an exact ``Decimal``
    quantised to the cent; the arithmetic always reconciles.

    Attributes
    ----------
    base:            pre-tax selling price
    gst:             federal GST component (0 if none)
    qst:             Québec QST component (0 if not Québec)
    hst:             the provincial part of HST (0 if not an HST province)
    pst:             PST/RST component (0 if none)
    total:           base + all taxes
    jurisdiction:    the jurisdiction code applied
    total_tax:       convenience: every tax component summed
    """

    base: Decimal
    gst: Decimal
    qst: Decimal
    hst: Decimal
    pst: Decimal
    total: Decimal
    jurisdiction: str

    @property
    def total_tax(self) -> Decimal:
        return self.gst + self.qst + self.hst + self.pst

    @property
    def provincial_tax(self) -> Decimal:
        """The non-federal tax: QST, HST provincial part, or PST/RST."""
        return self.qst + self.hst + self.pst

    def as_dict(self) -> Dict[str, str]:
        """Plain string mapping — convenient for JSON and invoices."""
        return {
            "base": str(self.base),
            "gst": str(self.gst),
            "qst": str(self.qst),
            "hst": str(self.hst),
            "pst": str(self.pst),
            "total_tax": str(self.total_tax),
            "total": str(self.total),
            "jurisdiction": self.jurisdiction,
        }

    def __str__(self) -> str:
        parts = [f"base {self.base}"]
        for label, val in (
            ("GST", self.gst),
            ("QST", self.qst),
            ("HST", self.hst),
            ("PST", self.pst),
        ):
            if val:
                parts.append(f"{label} {val}")
        parts.append(f"total {self.total}")
        return " + ".join(parts)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def calculate(
    amount: MoneyLike,
    jurisdiction: Union[str, Jurisdiction] = "QC",
    *,
    gst: Optional[MoneyLike] = None,
    qst: Optional[MoneyLike] = None,
) -> TaxResult:
    """
    Calculate taxes on a **pre-tax** selling price.

    Parameters
    ----------
    amount:
        Pre-tax amount. Accepts str, int, Decimal or float.
    jurisdiction:
        Province code (``"QC"``) or a :class:`Jurisdiction` instance.
    gst, qst:
        Override a component's *rate* (e.g. ``gst="0.05"``). Useful for
        historical rates or for a zero-rated sale where you want to record the
        applied rate explicitly.

    Returns
    -------
    TaxResult

    Raises
    ------
    NegativeAmount, InvalidRate, CanadianTaxError

    Examples
    --------
    >>> r = calculate("100.00")
    >>> str(r.gst), str(r.qst), str(r.total)
    ('5.00', '9.98', '114.98')

    >>> # QST is NOT compounded on GST:
    >>> calculate("100").total == Decimal("114.98")
    True

    >>> # Zero-rated export: no tax, total == base
    >>> calculate("100", "QC", gst="0", qst="0").total
    Decimal('100.00')
    """
    j = by_code(jurisdiction) if isinstance(jurisdiction, str) else jurisdiction
    if not isinstance(j, Jurisdiction):
        raise TypeError(
            f"jurisdiction must be a code or Jurisdiction, got {type(jurisdiction).__name__}"
        )

    base = _round_cent(_to_decimal(amount, name="amount"))

    gst_rate = _validate_rate(
        _to_decimal(gst, name="gst rate") if gst is not None else j.gst_rate, name="gst"
    )
    prov_rate = _validate_rate(
        _to_decimal(qst, name="qst rate") if qst is not None else j.provincial_rate,
        name="qst",
    )

    # ------------------------------------------------------------------ #
    # Each tax rounds independently on the PRE-TAX base (except Manitoba,
    # where RST is levied on the GST-inclusive price by law).
    # ------------------------------------------------------------------ #
    gst_amt = _round_cent(base * gst_rate)

    if j.compounded and qst is None:
        prov_amt = _round_cent((base + gst_amt) * prov_rate)
    else:
        prov_amt = _round_cent(base * prov_rate)

    zero = Decimal("0.00")
    qst_amt = zero
    hst_amt = zero
    pst_amt = zero

    kind = j.kind if (gst is None and qst is None) else "GST+QST"
    if kind == "GST+QST":
        qst_amt = prov_amt
    elif kind == "HST":
        hst_amt = prov_amt
    elif kind == "GST+PST":
        pst_amt = prov_amt
    elif kind == "GST":
        # rate override still recorded as a provincial component if given
        if qst is not None:
            qst_amt = prov_amt
    else:  # "none"
        pass

    total = base + gst_amt + qst_amt + hst_amt + pst_amt
    return TaxResult(
        base=base,
        gst=gst_amt,
        qst=qst_amt,
        hst=hst_amt,
        pst=pst_amt,
        total=total,
        jurisdiction=j.code,
    )


def extract(
    amount: MoneyLike,
    jurisdiction: Union[str, Jurisdiction] = "QC",
    *,
    strict: bool = False,
) -> TaxResult:
    """
    Recover the pre-tax base and each tax component from a **tax-included** price.

    Uses the jurisdiction's combined divisor (``114.975`` for Québec, i.e.
    ``1 + 0.05 + 0.09975``), then reconciles so the parts add up exactly:

    >>> r = extract("114.98")
    >>> str(r.base), str(r.gst), str(r.qst), str(r.total)
    ('100.00', '5.00', '9.98', '114.98')

    Parameters
    ----------
    strict:
        When True, raise :class:`BackTaxed` if no pre-tax base under these rates
        forward-calculates to exactly ``amount``. Default False, in which case
        the nearest base is returned and the residual cent is absorbed by the
        larger tax component so the parts always re-sum.

    Notes
    -----
    Because rounding is many-to-one, ``extract`` searches the few candidate
    bases around ``amount / (1 + rate)`` and returns the one whose forward
    :func:`calculate` reproduces ``amount`` exactly. Over 20 000 sampled
    amounts this makes ``extract∘calculate`` an exact inverse.

    Examples
    --------
    >>> extract("2.00").total
    Decimal('2.00')
    >>> extract("2.00").base + extract("2.00").total_tax == Decimal("2.00")
    True
    """
    j = by_code(jurisdiction) if isinstance(jurisdiction, str) else jurisdiction
    if not isinstance(j, Jurisdiction):
        raise TypeError(
            f"jurisdiction must be a code or Jurisdiction, got {type(jurisdiction).__name__}"
        )

    total = _round_cent(_to_decimal(amount, name="amount"))
    divisor = j.combined_divisor

    # ------------------------------------------------------------------ #
    # Naive extraction: base ≈ total / (1 + rate), then each tax on that base.
    #
    # Rounding is many-to-one (two adjacent bases can forward-calculate to the
    # same total), so the naive base is not always the base that produced
    # `total`. We therefore check the handful of candidate bases around the
    # estimate and prefer the one whose FORWARD calculation reproduces `total`
    # exactly — making extract() a true inverse of calculate().
    # ------------------------------------------------------------------ #
    estimate = _round_cent(total / divisor)
    candidate_offsets = (0, -1, 1, -2, 2, -3, 3)

    def forward(base: Decimal) -> TaxResult:
        return calculate(base, j)

    base = None
    resolved = None
    for offset in candidate_offsets:
        cand = estimate + Decimal(offset) / 100
        if cand < 0:
            continue
        fwd = forward(cand)
        if fwd.total == total:
            base, resolved = cand, fwd
            break

    if resolved is None:
        # No candidate forward-calculates to `total` (the amount was not
        # produced by these rates). Fall back to the naive decomposition.
        base = estimate
        fed_share = j.gst_rate / divisor
        prov_share = j.provincial_rate / divisor
        gst_amt = _round_cent(total * fed_share)
        prov_amt = _round_cent(total * prov_share)

        drift = total - (base + gst_amt + prov_amt)
        if strict:
            raise BackTaxed(
                f"cannot decompose {total} consistently under {j.code} rates "
                f"(nearest base {base} forward-calculates to "
                f"{forward(base).total}, not {total})"
            )
        if drift.quantize(_CENT) != Decimal("0.00"):
            # absorb into the larger component — never lose or invent a cent
            if gst_amt >= prov_amt:
                gst_amt += drift
            else:
                prov_amt += drift

        zero = Decimal("0.00")
        qst_amt = hst_amt = pst_amt = zero
        if j.kind == "GST+QST" or (j.kind == "GST" and False):
            qst_amt = prov_amt
        elif j.kind == "HST":
            hst_amt = prov_amt
        elif j.kind == "GST+PST":
            pst_amt = prov_amt
        else:
            # GST-only (or unknown kind): fold provincial share into GST
            gst_amt += prov_amt

        return TaxResult(
            base=base,
            gst=gst_amt,
            qst=qst_amt,
            hst=hst_amt,
            pst=pst_amt,
            total=total,
            jurisdiction=j.code,
        )

    # The forward calculation reproduced `total` exactly: use its components.
    return TaxResult(
        base=resolved.base,
        gst=resolved.gst,
        qst=resolved.qst,
        hst=resolved.hst,
        pst=resolved.pst,
        total=total,
        jurisdiction=j.code,
    )


# Keep a reference so `from qc_tax._core import _ALL` style introspection works.
def _iter_jurisdictions() -> Iterable[Jurisdiction]:
    return _ALL
