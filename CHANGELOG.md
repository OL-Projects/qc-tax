# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-11-06

First release.

### Added

- `calculate()` — tax on a pre-tax price for all 13 Canadian jurisdictions
  (GST, HST, QST, PST, RST). Matches Revenu Québec publication IN-256-V:
  `$100.00 → GST $5.00 + QST $9.98 = $114.98`.
- `extract()` — recover base and components from a tax-included amount, with a
  guaranteed exact inverse of `calculate()` and parts that always re-sum.
- `TaxResult` — frozen result object with `total_tax`, `provincial_tax` and a
  JSON-ready `as_dict()`.
- `format_money()` / `parse_money()` — `en-CA` and `fr-CA` money, narrow
  no-break spaces, and both decimal-separator conventions.
- `to_cents()` / `from_cents()` — integer-cent conversion without floats.
- `is_valid_sin()` / `validate_sin()` / `normalize_sin()` / `format_sin()` —
  offline Luhn checks that accept legitimately leading-zero SINs (e.g.
  `046 454 286`), which many validators wrongly reject.
- Rate overrides (`gst=`, `qst=`) for historical or zero-rated invoices.

### Notes

- 109 tests, including published reference figures, penny-boundary rounding and
  invariant sweeps over deterministic 300–500 amount samples.
- Zero runtime dependencies; Python 3.9+.
- Manitoba RST is applied to the pre-GST price (Info. Bulletin RST 001), so no
  Canadian jurisdiction compounds provincial tax on federal tax.

[1.0.0]: https://github.com/OL-Projects/qc-tax/releases/tag/v1.0.0
