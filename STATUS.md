# qc-tax — OSS package status

**Purpose:** reputation and inbound, not revenue. A narrow, genuinely-correct
library that Québec/Canadian developers search for and then find OL's name on.

**Repo:** https://github.com/OL-Projects/qc-tax
**Local:** `~/.ol/business/oss/`

---

## Why this package (the wedge)

The Québec tax-arithmetic niche is full of *wrong* implementations, and the
errors are specific and diagnosable — which makes them searchable:

1. **QST compounded on GST.** The single most common invoicing bug. Anyone who
   has overcharged a customer searches exactly this.
2. **Float money / banker's rounding.** `round(2.675, 2) == 2.67`.
3. **Reverse tax from a tax-included price** using the wrong divisor.
4. **SIN validators that reject leading-zero SINs** — including ones the CRA
   publishes itself.

`qc-tax` is correct on all four and proves it with tests, which is the whole
pitch. The README leads with the bugs rather than the API.

## What was actually built and verified

| Item | Status | Evidence |
|------|--------|----------|
| Library | done | `qc_tax/` — `_core.py`, `_format.py`, `_sin.py` |
| Tests | **109 passing** | from source, extracted sdist, **and a fresh public clone** |
| Doctests | 7 passing | `pytest --doctest-modules qc_tax/` |
| Build | clean | `python -m build` → wheel + sdist in `dist/` |
| Metadata | PASSED | `twine check dist/*` |
| Clean-install smoke | works | sdist → fresh venv → correct numbers |
| GitHub | **live** | https://github.com/OL-Projects/qc-tax (public, v1.0.0 tagged) |
| Jurisdictions | 10 checked against 2026 published rates | `eff` column verified |

### Correctness anchors (each verified against the primary source)
- `$100.00 → GST $5.00 + QST $9.98 = $114.98` — Revenu Québec **IN-256-V**.
- `extract()` is a **true inverse**: 20,000 sampled amounts, **0 failures**
  (the naive implementation failed ~16%, which was the most valuable bug found).
- Manitoba RST is on the **pre-GST** price (MB Information Bulletin **RST 001**)
  — an initial compounding assumption was wrong and was corrected against it.
- Nova Scotia HST is **14%** since 1 April 2025 (CRA **Notice 342**).
- A leading-zero SIN is legal — the CRA publishes **`046 454 286`** as its own
  example, which several popular validators wrongly reject.

## What still blocks publishing

**Exactly one thing: a PyPI upload credential.** The package is otherwise
complete and verified — built artifacts pass `twine check`, install cleanly, and
the shipped test suite passes from a fresh public clone.

1. **No PyPI account/token.** Owner action required:
   - create/link the PyPI account, then either
   - generate a scoped API token (project: `qc-tax`), or
   - **preferred:** set up Trusted Publishing pointing at
     `OL-Projects/qc-tax` + workflow `publish.yml` (no stored secret).
2. **Confirm the public author email** — currently `ol@ol-services.ca`; this
   becomes visible on the PyPI package page.
3. Optional hardening: a `publish.yml` workflow on tag push (needs the trusted
   publisher in place first, so it was deliberately not added yet — a workflow
   that can't authenticate is worse than none).

Repo, tag, description and topics are all done. Nothing else is missing.

## Publish procedure (once the token exists)

```bash
cd ~/.ol/business/oss
gh repo create OL-Projects/qc-tax --public --source=. --push
git tag -a v1.0.0 -m "qc-tax 1.0.0"
git push origin v1.0.0
rm -rf build dist *.egg-info && python -m build
twine check dist/*
twine upload dist/*        # TWINE_USERNAME=__token__ TWINE_PASSWORD=pypi-...
```

**Preferred over a token:** PyPI Trusted Publishing — add a publisher on PyPI
pointing at `OL-Projects/qc-tax`, workflow `publish.yml`, and the upload needs
no stored secret. Worth doing first for a package meant to be maintained.

## Post-publish inbound plan (not done — belongs to a follow-up)

- `pip install qc-tax` then a short "how to fix compounded QST" post.
- Answer the recurring StackOverflow/Réedit r/Quebec + r/PersonalFinanceCanada
  questions on QST-on-GST with a worked example, linking the repo.
- Optional: a one-page `qc-tax` invoice calculator hosted on ol-services.ca as
  the top-of-funnel.
