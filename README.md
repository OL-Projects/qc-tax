# qc-tax

**Exact-to-the-cent Canadian sales tax math.** Québec GST/QST, HST, PST/RST, plus Canadian SIN validation — in integer cents, with no floating-point damage and no compounded-QST bug.

[![Tests](https://github.com/OL-Projects/qc-tax/actions/workflows/tests.yml/badge.svg)](https://github.com/OL-Projects/qc-tax/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

```python
>>> from qc_tax import calculate
>>> r = calculate("100.00")
>>> r.gst, r.qst, r.total
(Decimal('5.00'), Decimal('9.98'), Decimal('114.98'))
```

Matches Revenu Québec publication **IN-256-V** exactly: `$100.00 → GST $5.00 + QST $9.98 = $114.98`.

---

## The five bugs this package exists to prevent

### 1. Compounding QST on top of GST

QST is **not** a tax on the GST. Both taxes apply to the *pre-tax selling price*. The single most common Québec invoicing error:

```python
# WRONG — QST charged on the GST-inclusive amount
subtotal = 100.00
gst = subtotal * 0.05           # 5.00
qst = (subtotal + gst) * 0.09975  # 10.47  ← over-charges your customer

# RIGHT
>>> calculate("100").qst
Decimal('9.98')
```

### 2. Rounding pre-tax, then rounding the total

Each tax rounds to the cent **independently and before** summing:

| Amount | GST (5%) | QST (9.975%) | Total |
|-------:|---------:|-------------:|------:|
| $0.50  | $0.03    | $0.05        | $0.58 |
| $1.00  | $0.05    | $0.10        | $1.15 |
| $9.99  | $0.50    | $1.00        | $11.49 |
| $100.00| $5.00    | $9.98        | $114.98 |

### 3. Float money

`round()` on floats is **banker's rounding** (half-to-even) and carries binary noise. `qc-tax` uses `Decimal` throughout with `ROUND_HALF_UP` — the rule tax authorities specify.

```python
>>> round(2.675, 2)          # 2.67  ← classic float surprise
>>> format_money("2.675")    # '$2.68'
```

### 4. Extracting tax from a tax-included price

To go backwards you divide by **`1 + both rates`** (114.975 for Québec), not by one rate:

```python
>>> from qc_tax import extract
>>> r = extract("114.98")
>>> r.base, r.gst, r.qst
(Decimal('100.00'), Decimal('5.00'), Decimal('9.98'))
```

`extract()` is a **true inverse** of `calculate()`: it searches the candidate bases around the estimate and returns the one that forward-calculates to exactly the amount you gave it. Verified over 20,000 sampled amounts with zero failures. Any residual rounding cent is absorbed so `base + gst + qst` always re-sums to the input — your invoice never fails to add up.

### 5. SIN validators that reject valid SINs

Many open-source SIN validators reject numbers starting with `0`. Those are **real, issued SINs** — the CRA's own published example is `046 454 286`.

```python
>>> from qc_tax import is_valid_sin, format_sin
>>> is_valid_sin("046 454 286")   # leading zero is legal
True
>>> format_sin("046454286")
'046 454 286'
>>> is_valid_sin("000 000 000")   # never issued
False
```

---

## Install

```bash
pip install qc-tax
```

Zero runtime dependencies. Python 3.9+.

## Usage

### Calculating tax

```python
from qc_tax import calculate, Ontario, Alberta

calculate("100.00")              # Québec: GST 5.00 + QST 9.98 = 114.98
calculate("100.00", "ON")        # Ontario HST: GST 5.00 + HST 8.00 = 113.00
calculate("100.00", Alberta)     # Alberta: GST 5.00 = 105.00
calculate("100.00", gst="0", qst="0")   # zero-rated export: total 100.00
```

### Every jurisdiction

| Code | Jurisdiction | Tax | Effective rate |
|------|--------------|-----|----------------|
| `QC` | Québec | GST 5% + QST 9.975% | 14.975% |
| `ON` | Ontario | HST 13% | 13% |
| `NS` | Nova Scotia | HST 14% | 14% |
| `NB`, `NL`, `PE` | New Brunswick, Newfoundland & Labrador, PEI | HST 15% | 15% |
| `BC` | British Columbia | GST 5% + PST 7% | 12% |
| `SK` | Saskatchewan | GST 5% + PST 6% | 11% |
| `MB` | Manitoba | GST 5% + RST 7% | 12% |
| `AB`, `YT`/`NT`/`NU` | Alberta, Territories | GST 5% | 5% |

**No Canadian jurisdiction compounds.** Québec's QST is not charged on the GST, and Manitoba's RST applies to the pre-GST price (Manitoba Finance, Information Bulletin RST 001) — so every effective rate above is a plain sum of its parts. On $100 in Manitoba: $5.00 GST + $7.00 RST = $112.00.

### Formatting

Both Canadian locales, because they disagree on the decimal separator:

```python
>>> from qc_tax import format_money, parse_money
>>> format_money("1234.56")
'$1,234.56'
>>> format_money("1234.56", locale="fr-CA")
'1\u202f234,56 $'          # narrow no-break spaces, trailing symbol
>>> parse_money("1 234,56 $")
Decimal('1234.56')
```

### The result object

```python
>>> r = calculate("100.00")
>>> r.as_dict()
{'base': '100.00', 'gst': '5.00', 'qst': '9.98', 'hst': '0.00',
 'pst': '0.00', 'total_tax': '14.98', 'total': '114.98', 'jurisdiction': 'QC'}
>>> r.total_tax
Decimal('14.98')
>>> r.provincial_tax     # QST, HST provincial part, or PST
Decimal('9.98')
```

## What this is not

- **Not tax advice.** Confirm rates and your obligations with Revenu Québec or the CRA.
- **Not a filing tool.** It computes numbers; it does not submit returns.
- **Not SIN verification.** `is_valid_sin` is an **offline Luhn check**. It tells you a number is *well-formed*, not that ESDC *issued* it. Real SIN confirmation is a paid, employer-only service.
- **Rates are 2026.** Rates move: Nova Scotia's HST fell from 15% to 14% on 1 April 2025, and PEI's provincial component rose to 10% (15% HST) in 2016. Pass `gst=`/`qst=` to override for historical invoices.

## Testing

```bash
pip install -e ".[test]"
pytest                       # 108 tests
pytest --doctest-modules qc_tax/
```

The suite pins the published Revenu Québec worked example, checks penny-boundary rounding, and proves invariants over a deterministic 300–500 amount sample (components always re-sum; `extract` is an exact inverse; every result is two decimals).

## License

MIT. See [LICENSE](LICENSE).
