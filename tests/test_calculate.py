"""
Tax-calculation tests.

The first class of tests pins the numbers Revenu Québec publishes; the second
proves *invariants* hold over a large deterministic sample, which is what
actually guarantees the package can be trusted on money.
"""

from decimal import Decimal

import pytest

from qc_tax import (
    Alberta,
    BritishColumbia,
    InvalidRate,
    Manitoba,
    NegativeAmount,
    Ontario,
    Quebec,
    by_code,
    calculate,
    extract,
    rate_for,
    provinces,
)
from qc_tax._core import CanadianTaxError

from .conftest import money_samples


# --------------------------------------------------------------------------- #
# 1. Published reference figures
# --------------------------------------------------------------------------- #
class TestRevenuQuebecWorkedExample:
    """IN-256-V: $100.00 item → GST $5.00, QST $9.98, total $114.98."""

    def test_gst(self, rq_example):
        assert calculate(rq_example).gst == Decimal("5.00")

    def test_qst(self, rq_example):
        # 100 * 0.09975 = 9.975 -> rounds HALF_UP to 9.98 (not 9.97)
        assert calculate(rq_example).qst == Decimal("9.98")

    def test_total(self, rq_example):
        assert calculate(rq_example).total == Decimal("114.98")

    def test_qst_is_not_compounded_on_gst(self):
        """The classic error: 100 + 5% then QST on 105 = 10.47. Must be 9.98."""
        r = calculate("100")
        compounded = Decimal("105.00") * Decimal("0.09975")
        assert r.qst != compounded.quantize(Decimal("0.01"))
        assert r.qst == Decimal("9.98")


# --------------------------------------------------------------------------- #
# 2. Rounding behaviour
# --------------------------------------------------------------------------- #
class TestRounding:
    def test_half_up_not_bankers(self):
        # 0.09975 * 2 = 0.1995 exactly -> HALF_UP gives 0.20; HALF_EVEN gives 0.20
        # Construct a clean .5 case: base 0.10 -> QST 0.009975 -> 0.01
        assert calculate("0.10").qst == Decimal("0.01")

    @pytest.mark.parametrize(
        "amount,gst,qst",
        [
            ("0.01", "0.00", "0.00"),   # 0.0005 / 0.0009975 -> 0
            ("0.10", "0.01", "0.01"),
            ("0.50", "0.03", "0.05"),   # 0.025->0.03 HALF_UP, 0.049875->0.05
            ("1.00", "0.05", "0.10"),   # 0.09975 -> 0.10
            ("9.99", "0.50", "1.00"),
            ("10.00", "0.50", "1.00"),  # 0.9975 -> 1.00
        ],
    )
    def test_penny_boundaries(self, amount, gst, qst):
        r = calculate(amount)
        assert r.gst == Decimal(gst), f"GST on {amount}"
        assert r.qst == Decimal(qst), f"QST on {amount}"

    def test_qst_just_below_half_rounds_down(self):
        # 4.00 * 0.09975 = 0.399 -> 0.40 ; 3.00 -> 0.29925 -> 0.30
        assert calculate("3.00").qst == Decimal("0.30")

    def test_every_result_is_two_decimals(self):
        for amt in money_samples(200):
            r = calculate(amt)
            for v in (r.base, r.gst, r.qst, r.total):
                assert v.as_tuple().exponent == -2, f"{amt} produced {v}"


# --------------------------------------------------------------------------- #
# 3. Invariants over a large sample
# --------------------------------------------------------------------------- #
class TestInvariants:
    def test_total_equals_components(self):
        for amt in money_samples():
            r = calculate(amt)
            assert r.base + r.gst + r.qst == r.total, f"broken at {amt}"

    def test_non_negative_components(self):
        for amt in money_samples():
            r = calculate(amt)
            assert r.gst >= 0 and r.qst >= 0 and r.total >= 0

    def test_total_tax_matches_sum(self):
        for amt in money_samples(100):
            r = calculate(amt)
            assert r.total_tax == r.gst + r.qst

    def test_effective_rate_is_14_975_percent(self):
        for amt in money_samples(100, high=Decimal("10000")):
            r = calculate(amt)
            implied = (r.total - r.base) / r.base
            # allow up to 1 cent of rounding error per component
            slack = Decimal("0.02") / r.base
            assert abs(implied - Decimal("0.14975")) <= slack, f"{amt} -> {implied}"


# --------------------------------------------------------------------------- #
# 4. extract(): the inverse operation
# --------------------------------------------------------------------------- #
class TestExtract:
    def test_recovers_the_rq_example(self):
        r = extract("114.98")
        assert r.base == Decimal("100.00")
        assert r.gst == Decimal("5.00")
        assert r.qst == Decimal("9.98")

    def test_roundtrip_on_large_sample(self):
        """
        calculate -> extract must be a true inverse: the recovered base must
        forward-calculate back to the same total, and the components must match
        the original ones exactly.
        """
        failures = []
        for amt in money_samples(300):
            fwd = calculate(amt)
            back = extract(fwd.total)
            if (
                back.base != fwd.base
                or back.gst != fwd.gst
                or back.qst != fwd.qst
                or back.total != fwd.total
            ):
                failures.append((amt, fwd, back))
        assert not failures, f"{len(failures)} roundtrip mismatches, e.g. {failures[:3]}"

    def test_recovered_base_recalculates_to_the_same_total(self):
        """The property an invoice system actually depends on."""
        failures = []
        for amt in money_samples(500):
            fwd = calculate(amt)
            back = extract(fwd.total)
            if calculate(back.base).total != fwd.total:
                failures.append((amt, back.base, fwd.total, calculate(back.base).total))
        assert not failures, f"{len(failures)} unstable, e.g. {failures[:3]}"

    def test_parts_always_resum_to_the_input(self):
        for amt in money_samples(300):
            r = extract(amt)
            assert r.base + r.gst + r.qst == r.total, f"extract({amt}) does not re-sum"

    def test_strict_mode_accepts_valid_tax_included_amounts(self):
        r = extract("114.98", strict=True)
        assert r.total == Decimal("114.98")

    def test_cent_amounts_extract_cleanly(self):
        r = extract("2.00")
        assert r.base + r.gst + r.qst == r.total

    def test_zero(self):
        r = extract("0.00")
        assert r.base == 0 and r.gst == 0 and r.qst == 0


# --------------------------------------------------------------------------- #
# 5. Other jurisdictions
# --------------------------------------------------------------------------- #
class TestJurisdictions:
    def test_ontario_hst_is_13_percent(self):
        r = calculate("100", Ontario)
        assert r.gst == Decimal("5.00")
        assert r.hst == Decimal("8.00")
        assert r.qst == 0
        assert r.total == Decimal("113.00")

    def test_alberta_is_gst_only(self):
        r = calculate("100", Alberta)
        assert r.gst == Decimal("5.00")
        assert r.provincial_tax == 0
        assert r.total == Decimal("105.00")

    def test_bc_has_pst_but_hst_does_not_apply(self):
        r = calculate("100", BritishColumbia)
        assert r.hst == 0
        assert r.pst == Decimal("7.00")
        assert r.total == Decimal("112.00")

    def test_manitoba_rst_is_on_the_pre_gst_price(self):
        """
        Manitoba Finance, Information Bulletin RST 001: RST applies to the
        selling price *before* GST. On $100: GST 5.00, RST 7.00, total 112.00.
        """
        r = calculate("100", Manitoba)
        assert r.gst == Decimal("5.00")
        assert r.pst == Decimal("7.00")
        assert r.total == Decimal("112.00")

    def test_no_canadian_jurisdiction_compounds(self):
        """Every jurisdiction's effective rate is a plain sum of its parts."""
        for j in provinces():
            assert j.compounded is False, f"{j.code} compounds unexpectedly"

    def test_quebec_is_the_only_compounding_free_qst_charge(self):
        r = calculate("100", Quebec)
        assert r.pst == 0 and r.hst == 0
        assert r.qst == Decimal("9.98")

    def test_rate_for(self):
        assert rate_for("QC") == Decimal("0.14975")
        assert rate_for("ON") == Decimal("0.13")
        assert rate_for("AB") == Decimal("0.05")

    def test_by_code_is_case_insensitive(self):
        assert by_code("qc") is Quebec
        assert by_code(" QC ") is Quebec

    def test_by_code_aliases(self):
        assert by_code("PQ") is Quebec
        assert by_code("PE") is by_code("PE")

    def test_unknown_code_raises(self):
        with pytest.raises(CanadianTaxError, match="unknown jurisdiction"):
            by_code("XX")

    def test_provinces_covers_all_thirteen_jurisdictions(self):
        codes = {j.code for j in provinces()}
        assert len(codes) == 11  # 10 provinces + 1 territories entry
        assert "QC" in codes and "ON" in codes and "YT/NT/NU" in codes


# --------------------------------------------------------------------------- #
# 6. Input handling
# --------------------------------------------------------------------------- #
class TestInputs:
    @pytest.mark.parametrize(
        "amount", ["100", "100.00", 100, 100.0, Decimal("100")]
    )
    def test_accepts_str_int_float_decimal(self, amount):
        assert calculate(amount).total == Decimal("114.98")

    def test_float_is_converted_through_repr_not_binary(self):
        # naive Decimal(114.98) picks up binary noise; we must not.
        # 114.98 * 1.14975 = 132.198255 -> 132.20
        r = calculate(114.98)
        assert r.base == Decimal("114.98")
        assert r.total == Decimal("132.20")

    def test_accepts_currency_symbol_and_spaces(self):
        assert calculate("$100.00").base == Decimal("100.00")

    def test_accepts_french_decimal_comma(self):
        assert calculate("100,00").base == Decimal("100.00")

    def test_negative_raises(self):
        with pytest.raises(NegativeAmount):
            calculate("-1.00")

    def test_bool_rejected(self):
        with pytest.raises(TypeError):
            calculate(True)

    def test_garbage_raises(self):
        with pytest.raises(CanadianTaxError):
            calculate("not money")

    def test_empty_raises(self):
        with pytest.raises(CanadianTaxError):
            calculate("   ")

    def test_rate_override_zero_rates_a_zero_rated_sale(self):
        r = calculate("100", "QC", gst="0", qst="0")
        assert r.total == Decimal("100.00")
        assert r.total_tax == 0

    def test_invalid_rate_rejected(self):
        with pytest.raises(InvalidRate):
            calculate("100", "QC", gst="1.5")

    def test_custom_historical_rate(self):
        # QST was 9.5% before 2013.
        r = calculate("100", "QC", qst="0.095")
        assert r.qst == Decimal("9.50")


# --------------------------------------------------------------------------- #
# 7. Result object ergonomics
# --------------------------------------------------------------------------- #
class TestTaxResult:
    def test_frozen(self):
        r = calculate("100")
        with pytest.raises(Exception):
            r.base = Decimal("1")  # type: ignore[misc]

    def test_as_dict_is_json_ready(self):
        d = calculate("100").as_dict()
        assert d["total"] == "114.98"
        assert d["jurisdiction"] == "QC"
        assert all(isinstance(v, str) for v in d.values())

    def test_str_is_readable(self):
        s = str(calculate("100"))
        assert "114.98" in s and "QST" in s and "GST" in s

    def test_provincial_tax_alias(self):
        assert calculate("100").provincial_tax == Decimal("9.98")
