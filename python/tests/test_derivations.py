"""Derivation tests."""

from __future__ import annotations

from datetime import date

from static_validator.derivations import (
    DEFAULT_BDC,
    DEFAULT_CALENDAR,
    _add_months,
    _derive_first_coupon_date,
    _derive_issue_date,
    apply_derivations,
)


class TestAddMonths:
    def test_simple_forward(self):
        assert _add_months(date(2026, 1, 15), 6) == date(2026, 7, 15)

    def test_simple_backward(self):
        assert _add_months(date(2026, 7, 15), -6) == date(2026, 1, 15)

    def test_year_rollover(self):
        assert _add_months(date(2026, 12, 15), 1) == date(2027, 1, 15)

    def test_eom_clamp(self):
        # 2026-03-31 minus 1 month must clamp to 2026-02-28.
        assert _add_months(date(2026, 3, 31), -1) == date(2026, 2, 28)

    def test_eom_leap_year(self):
        assert _add_months(date(2024, 3, 31), -1) == date(2024, 2, 29)


class TestDeriveFirstCouponDate:
    def test_panama_2060_with_explicit_issue(self):
        # Panama 3.87% 2060-07-23, semi-annual, issued 2020-09-30.
        # First coupon should be 2021-01-23 — but the derivation walks back
        # from maturity in 6-month steps until just before issue date.
        first = _derive_first_coupon_date(
            maturity=date(2060, 7, 23),
            frequency=2,
            issue=date(2020, 9, 30),
        )
        # Walk back by 6 months from 2060-07-23 until just before 2020-09-30.
        # That lands on 2021-01-23. (Actual prospectus matches.)
        assert first == date(2021, 1, 23)

    def test_no_issue_uses_100yr_floor(self):
        first = _derive_first_coupon_date(
            maturity=date(2034, 7, 15),
            frequency=2,
            issue=None,
        )
        # Without an issue date, derivation walks back from maturity to a
        # date on or after (today - 100yr). Must produce a date and not loop.
        assert first.month == 7 or first.month == 1
        assert first <= date(2034, 7, 15)


class TestDeriveIssueDate:
    def test_semi_annual(self):
        issue = _derive_issue_date(date(2021, 1, 23), 2)
        assert issue == date(2020, 7, 23)


class TestApplyDerivations:
    def test_explicit_values_not_overwritten(self):
        rec = {
            "isin": "US698299BL70",
            "coupon": 3.87,
            "maturity_date": "2060-07-23",
            "frequency": 2,
            "day_count": "BOND_BASIS_30_360",
            "issue_date": "2020-09-30",
            "first_coupon_date": "2021-01-23",
            "calendar": "US_GOVERNMENT",
        }
        out = apply_derivations(rec)
        assert out["issue_date"] == "2020-09-30"
        assert out["first_coupon_date"] == "2021-01-23"
        assert out["calendar"] == "US_GOVERNMENT"
        assert out["business_day_convention"] == DEFAULT_BDC  # filled by default

    def test_fills_missing_dates(self):
        rec = {
            "isin": "US698299BL70",
            "coupon": 3.87,
            "maturity_date": "2060-07-23",
            "frequency": 2,
            "day_count": "BOND_BASIS_30_360",
        }
        out = apply_derivations(rec)
        assert "first_coupon_date" in out
        assert "issue_date" in out
        assert out["calendar"] == DEFAULT_CALENDAR
        assert out["business_day_convention"] == DEFAULT_BDC

    def test_zero_coupon_no_derivation(self):
        rec = {
            "isin": "US912828YY08",
            "coupon": 0,
            "maturity_date": "2030-01-15",
            "frequency": 0,
            "day_count": "ACT_ACT_ICMA",
        }
        out = apply_derivations(rec)
        # Zero-coupon: no period to derive from, so optional date fields
        # remain absent.
        assert "first_coupon_date" not in out
        assert "issue_date" not in out
