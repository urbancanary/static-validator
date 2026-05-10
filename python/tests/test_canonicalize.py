"""Canonical JSON tests."""

from __future__ import annotations

import pytest

from static_validator.canonicalize import (
    _normalize_number,
    _serialize_string_literal,
    _serialize_value,
    _validate_isin_checksum,
    canonicalize_json,
    canonicalize_record,
)


class TestIsinChecksum:
    def test_known_valid(self):
        # PANAMA 3.87% 2060
        assert _validate_isin_checksum("US698299BL70")
        # Indonesia 3.8% 2050
        assert _validate_isin_checksum("US71567RAQ92")

    def test_known_invalid(self):
        assert not _validate_isin_checksum("US698299BL71")
        assert not _validate_isin_checksum("US000000AAA0")


class TestNumberNormalization:
    @pytest.mark.parametrize(
        "given,expected",
        [
            (4.5, 4.5),
            ("4.5", 4.5),
            ("4.50", 4.5),
            ("4.500000", 4.5),
            (4, 4),
            ("4", 4),
            ("4.0", 4),
            (0, 0),
            (-0.0, 0),
            ("-0", 0),
            (3.87, 3.87),
            ("0.125", 0.125),
        ],
    )
    def test_normalize(self, given, expected):
        assert _normalize_number(given) == expected

    def test_booleans_rejected(self):
        with pytest.raises(ValueError):
            _normalize_number(True)


class TestStringEscaping:
    def test_basic(self):
        assert _serialize_string_literal("hello") == '"hello"'

    def test_quote_escape(self):
        assert _serialize_string_literal('a"b') == '"a\\"b"'

    def test_backslash_escape(self):
        assert _serialize_string_literal("a\\b") == '"a\\\\b"'

    def test_control_character_escape(self):
        assert _serialize_string_literal("\x01") == '"\\u0001"'
        assert _serialize_string_literal("\n") == '"\\n"'

    def test_no_unnecessary_unicode_escape(self):
        # NFC characters above U+001F must be passed through, not \uXXXX'd.
        assert _serialize_string_literal("café") == '"café"'


class TestSerialization:
    def test_object_keys_sorted(self):
        obj = {"b": 1, "a": 2}
        assert _serialize_value(obj) == '{"a":2,"b":1}'

    def test_no_whitespace(self):
        obj = {"a": [1, 2, 3], "b": {"nested": True}}
        assert _serialize_value(obj) == '{"a":[1,2,3],"b":{"nested":true}}'

    def test_null_forbidden(self):
        with pytest.raises(ValueError):
            _serialize_value(None)


class TestCanonicalizeRecord:
    def test_minimal_valid(self):
        rec = canonicalize_record(
            {
                "isin": "US698299BL70",
                "coupon": 3.87,
                "maturity_date": "2060-07-23",
                "frequency": 2,
                "day_count": "BOND_BASIS_30_360",
            }
        )
        assert rec["isin"] == "US698299BL70"
        assert rec["coupon"] == 3.87
        assert rec["frequency"] == 2

    def test_invalid_frequency(self):
        with pytest.raises(ValueError):
            canonicalize_record(
                {
                    "isin": "US698299BL70",
                    "coupon": 3.87,
                    "maturity_date": "2060-07-23",
                    "frequency": 3,  # invalid
                    "day_count": "BOND_BASIS_30_360",
                }
            )

    def test_invalid_isin_format(self):
        with pytest.raises(ValueError):
            canonicalize_record(
                {
                    "isin": "BAD",
                    "coupon": 3.87,
                    "maturity_date": "2060-07-23",
                    "frequency": 2,
                    "day_count": "BOND_BASIS_30_360",
                }
            )

    def test_invalid_isin_checksum(self):
        with pytest.raises(ValueError, match="checksum"):
            canonicalize_record(
                {
                    "isin": "US698299BL71",
                    "coupon": 3.87,
                    "maturity_date": "2060-07-23",
                    "frequency": 2,
                    "day_count": "BOND_BASIS_30_360",
                }
            )


class TestCanonicalizeJson:
    def test_byte_identical_for_equivalent_inputs(self):
        # Same logical input expressed differently must produce identical JSON.
        a = canonicalize_json(
            {
                "isin": "US698299BL70",
                "coupon": 3.87,
                "maturity_date": "2060-07-23",
                "frequency": 2,
                "day_count": "BOND_BASIS_30_360",
            }
        )
        b = canonicalize_json(
            {
                "day_count": "BOND_BASIS_30_360",
                "frequency": 2,
                "maturity_date": "2060-07-23",
                "coupon": "3.870000",  # different string, same number
                "isin": "US698299BL70",
            }
        )
        assert a == b
        # Verify expected canonical form: keys sorted, no whitespace.
        assert a == (
            '{"coupon":3.87,"day_count":"BOND_BASIS_30_360","frequency":2,'
            '"isin":"US698299BL70","maturity_date":"2060-07-23"}'
        )
