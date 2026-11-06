"""Tests for money formatting/parsing and SIN helpers."""

from decimal import Decimal

import pytest

from qc_tax import (
    InvalidSIN,
    format_money,
    format_money_cents,
    format_sin,
    is_valid_sin,
    normalize_sin,
    parse_money,
    to_cents,
    from_cents,
    validate_sin,
)


class TestFormatMoney:
    def test_default_en_ca(self):
        assert format_money("114.98") == "$114.98"

    def test_thousands_separator(self):
        assert format_money("1234567.89") == "$1,234,567.89"

    def test_fr_ca_uses_comma_and_trailing_symbol(self):
        assert format_money("114.98", locale="fr-CA") == "114,98 $"

    def test_fr_ca_thousands_use_narrow_nbsp(self):
        out = format_money("1234.56", locale="fr-CA")
        assert out == "1\u202f234,56 $"

    def test_no_symbol(self):
        assert format_money("5.00", symbol=False) == "5.00"

    def test_no_thousands(self):
        assert format_money("1234.56", thousands=False) == "$1234.56"

    def test_rounds_half_up(self):
        assert format_money(Decimal("2.675")) == "$2.68"

    def test_negative(self):
        assert format_money("-5.00") == "$-5.00"

    def test_float_input_does_not_leak_binary_noise(self):
        assert format_money(0.1 + 0.2) == "$0.30"


class TestFormatMoneyCents:
    def test_from_cents(self):
        assert format_money_cents(11498) == "$114.98"

    def test_rejects_non_int(self):
        with pytest.raises(TypeError):
            format_money_cents("11498")  # type: ignore[arg-type]

    def test_rejects_bool(self):
        with pytest.raises(TypeError):
            format_money_cents(True)  # type: ignore[arg-type]


class TestParseMoney:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("$114.98", "114.98"),
            ("114.98 $", "114.98"),
            ("1 234,56 $", "1234.56"),
            ("1\u00a0234,56", "1234.56"),
            ("1,234.56", "1234.56"),
            ("1.234,56", "1234.56"),   # European: last separator wins
            ("1,50", "1.50"),          # decimal comma, short tail
            ("1,234", "1234.00"),      # thousands, 3-digit tail
            ("CAD 50", "50.00"),
            ("0", "0.00"),
        ],
    )
    def test_parses_common_forms(self, text, expected):
        assert parse_money(text) == Decimal(expected)

    def test_roundtrips_with_format(self):
        for v in ("0.01", "5.00", "999.99", "1000000.00"):
            assert parse_money(format_money(v)) == Decimal(v)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            parse_money("   ")

    def test_garbage_raises(self):
        with pytest.raises(ValueError):
            parse_money("abc")

    def test_non_str_raises(self):
        with pytest.raises(TypeError):
            parse_money(12.34)  # type: ignore[arg-type]


class TestCents:
    def test_to_cents(self):
        assert to_cents("1.99") == 199
        assert to_cents(0.1 + 0.2) == 30

    def test_from_cents(self):
        assert from_cents(199) == Decimal("1.99")

    def test_roundtrip(self):
        for c in (0, 1, 99, 100, 12345, 999999):
            assert to_cents(from_cents(c)) == c


# --------------------------------------------------------------------------- #
# SIN
# --------------------------------------------------------------------------- #
class TestSIN:
    # The CRA's own published example.
    VALID = "046 454 286"

    def test_cra_example_is_valid(self):
        assert is_valid_sin(self.VALID) is True

    def test_leading_zero_is_legal(self):
        """A common validator bug is rejecting leading zeros; they are issued."""
        assert is_valid_sin("046-454-286") is True

    def test_bad_check_digit(self):
        assert is_valid_sin("046 454 287") is False

    def test_all_zero_rejected(self):
        assert is_valid_sin("000 000 000") is False

    @pytest.mark.parametrize(
        "bad", ["", "   ", "12345678", "1234567890", "abcdefghi", "046 454 28X", None]
    )
    def test_malformed_rejected(self, bad):
        assert is_valid_sin(bad) is False  # type: ignore[arg-type]

    def test_normalize_strips_all_separators(self):
        for form in ("046 454 286", "046-454-286", "046.454.286", " 046454286 "):
            assert normalize_sin(form) == "046454286"

    def test_normalize_preserves_leading_zero(self):
        assert normalize_sin("012 345 678") == "012345678"

    def test_normalize_int_losing_leading_zero_explains(self):
        with pytest.raises(InvalidSIN, match="leading zero"):
            normalize_sin(12345678)

    def test_normalize_accepts_full_length_int(self):
        assert normalize_sin(464542860) == "464542860"

    def test_validate_returns_normalized(self):
        assert validate_sin(self.VALID) == "046454286"

    def test_validate_raises_on_bad_check_digit(self):
        with pytest.raises(InvalidSIN, match="Luhn"):
            validate_sin("046 454 287")

    def test_validate_raises_on_all_zero(self):
        with pytest.raises(InvalidSIN):
            validate_sin("000 000 000")

    def test_format_space(self):
        assert format_sin("046454286") == "046 454 286"

    def test_format_dash(self):
        assert format_sin("046454286", style="dash") == "046-454-286"

    def test_format_plain(self):
        assert format_sin("046 454 286", style="plain") == "046454286"

    def test_format_rejects_bad_style(self):
        with pytest.raises(ValueError):
            format_sin("046454286", style="dots")

    def test_format_validates_first(self):
        with pytest.raises(InvalidSIN):
            format_sin("046 454 287")

    def test_luhn_known_valid_numbers(self):
        # Two well-formed numbers, each independently satisfying Luhn.
        for s in ("130 692 544", "046 454 286"):
            assert is_valid_sin(s) is True, s

    def test_invented_number_is_rejected(self):
        """A made-up 9-digit string almost never satisfies Luhn."""
        assert is_valid_sin("128 749 994") is False
        assert is_valid_sin("123 456 789") is False

    def test_bool_rejected(self):
        assert is_valid_sin(True) is False  # type: ignore[arg-type]
