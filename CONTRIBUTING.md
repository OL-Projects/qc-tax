# Contributing

Small, focused pull requests are welcome.

## Ground rules

1. **Never use `float` for money.** All internal arithmetic goes through
   `Decimal`, quantised to the cent with `ROUND_HALF_UP`.
2. **Every rate change needs a citation** to Revenu Québec, the CRA or a
   provincial finance ministry in the PR description and in a code comment.
   A rate without a source is a bug waiting to be filed.
3. **New behaviour needs a test that fails without it.** If you fix a rounding
   case, add the exact amount that exposed it.
4. **No runtime dependencies.** This package must stay installable anywhere.

## Running the tests

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"
pytest                       # unit tests
pytest --doctest-modules qc_tax/   # README/docstring examples
```

## Reporting a rounding bug

Please include:

- the pre-tax (or tax-included) amount,
- the jurisdiction,
- what the package returned,
- what the authority says it should be, ideally with a link.

## Scope

Out of scope: income tax, payroll, filing/remittance, and SIN *verification*
(which requires ESDC's paid registry service). Luhn validation is in scope.
