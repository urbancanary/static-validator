"""Tests for the normalization adapter (Layer A)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from static_validator.adapter import (
    disambiguate_bdc,
    disambiguate_calendar,
    disambiguate_day_count,
    normalize_coupon_value,
    normalize_frequency,
    normalize_to_published_record,
    parse_loose_date,
)

REPO_ROOT = Path(__file__).parents[2]
SCHEMA_DIR = REPO_ROOT / "schema"


PANAMA_ISIN = "US698299BL70"


# -------- day_count resolution tests --------

class TestDisambiguateDayCount_Direct:
    def test_canonical_raw_high_no_observations(self):
        # Lone canonical primary with no observations gets 'low' confidence —
        # the policy requires multi-source corroboration for high.
        res = disambiguate_day_count("BOND_BASIS_30_360", PANAMA_ISIN)
        assert res.canonical == "BOND_BASIS_30_360"
        assert res.confidence == "low"
        assert res.field_status == "explicit"

    def test_canonical_raw_plus_two_agreeing_observations_high(self):
        res = disambiguate_day_count(
            "BOND_BASIS_30_360", PANAMA_ISIN,
            observations={"emb": "BOND_BASIS_30_360", "cbonds": "BOND_BASIS_30_360"},
        )
        assert res.canonical == "BOND_BASIS_30_360"
        assert res.confidence == "high"
        assert "emb" in res.sources_used
        assert "cbonds" in res.sources_used

    def test_two_canonical_sources_medium(self):
        res = disambiguate_day_count(
            None, PANAMA_ISIN,
            observations={"emb": "ISMA_30_360", "lqd": "ISMA_30_360"},
        )
        assert res.canonical == "ISMA_30_360"
        assert res.confidence == "medium"


class TestDisambiguateDayCount_Ambiguous:
    def test_lone_30_360_unresolved(self):
        # The canonical 'this is the silent-drift case' regression: '30/360'
        # alone, no observations, no prospectus — must NOT auto-resolve.
        res = disambiguate_day_count("30/360", PANAMA_ISIN)
        assert res.canonical is None
        assert res.confidence == "unresolved"
        assert res.field_status == "unknown"
        # The reasoning must list the disambiguated alternatives.
        joined = " ".join(res.reasoning)
        assert "BOND_BASIS_30_360" in joined
        assert "ISMA_30_360" in joined

    def test_30_360_with_isin_hint_still_unresolved(self):
        # US-prefix sovereign — informational hint exists, but resolution
        # policy says hints are NEVER load-bearing.
        res = disambiguate_day_count("30/360", PANAMA_ISIN)
        assert res.canonical is None
        assert any("informational" in r for r in res.reasoning)

    def test_disagreeing_canonical_sources_unresolved(self):
        res = disambiguate_day_count(
            None, PANAMA_ISIN,
            observations={
                "emb": "BOND_BASIS_30_360",
                "lqd": "ISMA_30_360",
                "cemb": "BOND_BASIS_30_360",
            },
        )
        # 2 vs 1 — under conservative policy, plurality with 2 = medium,
        # not majority-vote auto-resolution. Verify.
        assert res.canonical == "BOND_BASIS_30_360"
        assert res.confidence == "medium"

    def test_three_way_split_unresolved(self):
        res = disambiguate_day_count(
            None, PANAMA_ISIN,
            observations={
                "a": "BOND_BASIS_30_360",
                "b": "ISMA_30_360",
                "c": "ISDA_30E_360",
            },
        )
        # No plurality — must mark unresolved.
        assert res.canonical is None
        assert res.confidence == "unresolved"


class TestDisambiguateDayCount_Prospectus:
    def test_panama_canonical_phrasing_resolves_high(self):
        # The actual prospectus excerpt from PANAMA's 424B5 (memory 260).
        res = disambiguate_day_count(
            "30/360", PANAMA_ISIN,
            prospectus_text=(
                "Interest will be computed on the basis of a 360-day year "
                "consisting of twelve 30-day months."
            ),
        )
        assert res.canonical == "BOND_BASIS_30_360"
        assert res.confidence == "high"
        assert "prospectus" in res.sources_used

    def test_isma_pinpoint_resolves(self):
        res = disambiguate_day_count(
            None, "XS1234567890",
            prospectus_text="day count: 30E/360 (ISMA)",
        )
        assert res.canonical == "ISMA_30_360"
        assert res.confidence == "high"

    def test_isda_pinpoint_resolves(self):
        res = disambiguate_day_count(
            None, "XS1234567890",
            prospectus_text="Interest accrual basis: 30E/360 (ISDA).",
        )
        assert res.canonical == "ISDA_30E_360"

    def test_eurobond_basis_phrase_maps_to_isda(self):
        res = disambiguate_day_count(
            None, "XS1234567890",
            prospectus_text="The day count fraction is Eurobond Basis.",
        )
        assert res.canonical == "ISDA_30E_360"


# -------- calendar / BDC tests --------

class TestDisambiguateCalendar:
    def test_null_raw_defaults(self):
        res = disambiguate_calendar(None, PANAMA_ISIN)
        assert res.canonical == "NULL_CALENDAR"
        assert res.field_status == "default"
        assert res.confidence == "high"

    def test_canonical_raw_accepted(self):
        res = disambiguate_calendar("US_GOVERNMENT", PANAMA_ISIN)
        assert res.canonical == "US_GOVERNMENT"
        assert res.field_status == "explicit"

    def test_unknown_string_unresolved(self):
        res = disambiguate_calendar("Tokyo", PANAMA_ISIN)
        assert res.canonical is None
        assert res.confidence == "unresolved"

    @pytest.mark.parametrize("raw, expected", [
        ("NYC", "US_SETTLEMENT"),
        ("New York", "US_SETTLEMENT"),
        ("nyse", "US_SETTLEMENT"),
        ("US Treasury", "US_GOVERNMENT"),
        ("FED", "US_GOVERNMENT"),
        ("EUR", "TARGET"),
        ("TARGET2", "TARGET"),
        ("ECB", "TARGET"),
        ("London", "UK_SETTLEMENT"),
        ("GBP", "UK_SETTLEMENT"),
        ("None", "NULL_CALENDAR"),
        ("Weekends", "WEEKENDS_ONLY"),
    ])
    def test_synonym_mapped(self, raw, expected):
        res = disambiguate_calendar(raw, PANAMA_ISIN)
        assert res.canonical == expected
        assert res.field_status == "explicit"
        assert any("synonym" in r for r in res.reasoning)

    @pytest.mark.parametrize("raw", ["US", "USD"])
    def test_us_alone_is_ambiguous(self, raw):
        res = disambiguate_calendar(raw, PANAMA_ISIN)
        assert res.canonical is None
        assert res.confidence == "unresolved"
        joined = " ".join(res.reasoning)
        assert "US_SETTLEMENT" in joined and "US_GOVERNMENT" in joined

    def test_observation_in_synonym_form_corroborates(self):
        # primary canonical, observation in shorthand form — must still count.
        res = disambiguate_calendar(
            "US_SETTLEMENT", PANAMA_ISIN,
            observations={"emb": "NYC", "lqd": "New York"},
        )
        assert res.canonical == "US_SETTLEMENT"
        assert res.confidence == "high"


class TestDisambiguateBdc:
    def test_null_raw_defaults(self):
        res = disambiguate_bdc(None, PANAMA_ISIN)
        assert res.canonical == "UNADJUSTED"
        assert res.field_status == "default"

    def test_unknown_string_unresolved(self):
        res = disambiguate_bdc("NEXT", PANAMA_ISIN)
        assert res.canonical is None

    @pytest.mark.parametrize("raw, expected", [
        ("MF", "MODIFIED_FOLLOWING"),
        ("Modified Following", "MODIFIED_FOLLOWING"),
        ("Mod Fol", "MODIFIED_FOLLOWING"),
        ("modified-following", "MODIFIED_FOLLOWING"),
        ("F", "FOLLOWING"),
        ("Fol", "FOLLOWING"),
        ("MP", "MODIFIED_PRECEDING"),
        ("Mod Prec", "MODIFIED_PRECEDING"),
        ("Preceding", "PRECEDING"),
        ("None", "UNADJUSTED"),
    ])
    def test_synonym_mapped(self, raw, expected):
        res = disambiguate_bdc(raw, PANAMA_ISIN)
        assert res.canonical == expected
        assert res.field_status == "explicit"


# -------- parse_loose_date --------

class TestParseLooseDate:
    @pytest.mark.parametrize("raw, expected", [
        ("2026-05-10", "2026-05-10"),
        ("20260510", "2026-05-10"),
        ("5-May-2026", "2026-05-05"),
        ("05 May 2026", "2026-05-05"),
        ("5/May/2026", "2026-05-05"),
        ("May 5, 2026", "2026-05-05"),
        ("May 5 2026", "2026-05-05"),
        ("September 1, 2030", "2030-09-01"),
        ("2026/05/10", "2026-05-10"),
    ])
    def test_unambiguous_formats_accepted(self, raw, expected):
        assert parse_loose_date(raw) == expected

    def test_date_object_accepted(self):
        assert parse_loose_date(date(2026, 5, 10)) == "2026-05-10"

    @pytest.mark.parametrize("raw", [
        "10/05/2026",     # DD/MM vs MM/DD — genuinely ambiguous
        "05/10/2026",
        "1/2/2026",
    ])
    def test_ambiguous_numeric_rejected(self, raw):
        with pytest.raises(ValueError, match="ambiguous"):
            parse_loose_date(raw)

    @pytest.mark.parametrize("raw, expected", [
        # reference 2026-05-10: pivot at 26. yy>=26 → 20yy, yy<26 → 21yy.
        ("5-May-26", "2026-05-05"),
        ("5-May-27", "2027-05-05"),
        ("5-May-99", "2099-05-05"),
        ("5-May-25", "2125-05-05"),
        ("5-May-00", "2100-05-05"),
        ("May 5, 56", "2056-05-05"),
        ("23-Jul-60", "2060-07-23"),
        ("23 Jul 24", "2124-07-23"),
    ])
    def test_two_digit_year_pivot_forward(self, raw, expected):
        assert parse_loose_date(raw, reference_date=date(2026, 5, 10)) == expected

    def test_two_digit_year_pivot_tracks_reference(self):
        # Same input, different reference date → different century.
        assert parse_loose_date("5-May-30", reference_date=date(2026, 5, 10)) == "2030-05-05"
        assert parse_loose_date("5-May-30", reference_date=date(2031, 1, 1)) == "2130-05-05"

    @pytest.mark.parametrize("raw, expected", [
        # reference 2026-05-10, backward pivot: yy<=26 → 20yy, yy>26 → 19yy.
        ("30-Sep-20", "2020-09-30"),
        ("23-Jan-21", "2021-01-23"),
        ("5-May-26", "2026-05-05"),
        ("5-May-99", "1999-05-05"),
        ("5-May-27", "1927-05-05"),
        ("5-May-00", "2000-05-05"),
    ])
    def test_two_digit_year_pivot_backward(self, raw, expected):
        assert parse_loose_date(
            raw, reference_date=date(2026, 5, 10), assume_future_year=False,
        ) == expected

    def test_excel_serial_in_window_accepted(self):
        # 46152 == 2026-05-10 in Excel's 1900-based calendar.
        assert parse_loose_date(46152) == "2026-05-10"
        assert parse_loose_date(46152.0) == "2026-05-10"

    @pytest.mark.parametrize("raw", [1, 100, 100000, -1])
    def test_excel_serial_out_of_window_rejected(self, raw):
        with pytest.raises(ValueError, match="Excel-serial"):
            parse_loose_date(raw)

    @pytest.mark.parametrize("raw", ["", "   ", "tomorrow", "Q1 2026", "Mar"])
    def test_unrecognised_rejected(self, raw):
        with pytest.raises(ValueError):
            parse_loose_date(raw)

    def test_booleans_rejected(self):
        with pytest.raises(ValueError):
            parse_loose_date(True)


# -------- normalize_coupon_value --------

class TestNormalizeCoupon:
    @pytest.mark.parametrize("raw, expected", [
        (4.5, 4.5),
        ("4.5", 4.5),
        ("4.5%", 4.5),
        (5, 5),
        ("5", 5),
        (5.0, 5),                # whole number → int
        ("3.870000", 3.87),      # trailing zeros stripped
        (0, 0),                  # zero coupon allowed
        ("0", 0),
    ])
    def test_accepted(self, raw, expected):
        assert normalize_coupon_value(raw) == expected

    @pytest.mark.parametrize("raw", [0.045, "0.045", 0.001, 0.4999])
    def test_fraction_like_rejected_by_default(self, raw):
        with pytest.raises(ValueError, match="fraction"):
            normalize_coupon_value(raw)

    def test_fraction_like_allowed_with_opt_in(self):
        # Genuine sub-0.5% coupon (e.g. JGB) — opt-in passes through.
        assert normalize_coupon_value(0.1, allow_below_half_pct=True) == 0.1

    @pytest.mark.parametrize("raw", [-1, "-2.5"])
    def test_negative_rejected(self, raw):
        with pytest.raises(ValueError, match="negative"):
            normalize_coupon_value(raw)

    @pytest.mark.parametrize("raw", [101, "150"])
    def test_above_100_rejected(self, raw):
        with pytest.raises(ValueError, match="100"):
            normalize_coupon_value(raw)

    def test_booleans_rejected(self):
        with pytest.raises(ValueError):
            normalize_coupon_value(True)


# -------- normalize_frequency --------

class TestNormalizeFrequency:
    @pytest.mark.parametrize("raw, expected", [
        (0, 0), (1, 1), (2, 2), (4, 4), (12, 12),
        ("0", 0), ("2", 2),
        ("S", 2), ("s", 2), ("Semi", 2),
        ("Semi-Annual", 2), ("SemiAnnual", 2), ("semiannually", 2),
        ("A", 1), ("Annual", 1), ("annually", 1),
        ("Q", 4), ("Quarterly", 4),
        ("M", 12), ("Monthly", 12),
        ("Z", 0), ("Zero-Coupon", 0), ("None", 0),
    ])
    def test_accepted(self, raw, expected):
        assert normalize_frequency(raw) == expected

    @pytest.mark.parametrize("raw", [3, 6, 7, "weekly", "biennial", ""])
    def test_unrecognised_rejected(self, raw):
        with pytest.raises(ValueError):
            normalize_frequency(raw)

    def test_booleans_rejected(self):
        with pytest.raises(ValueError):
            normalize_frequency(True)


# -------- end-to-end normalize_to_published_record --------

class TestNormalizeToPublishedRecord:
    def test_panama_with_canonical_input_produces_full_record(self):
        record = normalize_to_published_record(
            raw_row={
                "coupon": 3.87,
                "maturity_date": "2060-07-23",
                "frequency": 2,
                "day_count": "BOND_BASIS_30_360",
                "issue_date": "2020-09-30",
                "first_coupon_date": "2021-01-23",
            },
            isin=PANAMA_ISIN,
            asof=date(2026, 5, 10),
            structural_flags={"is_bullet": False, "is_sinker": True},
            sources=[{"id": "EDGAR-424B5-0001193125-20-252589",
                       "kind": "prospectus"}],
        )
        assert record["isin"] == PANAMA_ISIN
        assert record["tier_hashes"]["calc_hash_min"].startswith("sha256:")
        assert record["canonical_field_status"]["day_count"] == "explicit"
        assert record["canonical_field_status"]["calendar"] == "default"
        assert record["confidence"] in ("low", "medium", "high")  # depends on observations

    def test_panama_with_ambiguous_day_count_omits_unresolved(self):
        # bond_identity-shape: '30/360' string, null first_coupon_date, null calendar.
        record = normalize_to_published_record(
            raw_row={
                "coupon": 3.87,
                "maturity_date": "2060-07-23",
                "frequency": 2,
                "day_count": "30/360",
                "issue_date": "2020-09-30",
                "first_coupon_date": None,
                "calendar": None,
                "business_day_convention": None,
            },
            isin=PANAMA_ISIN,
            asof=date(2026, 5, 10),
            structural_flags={"is_bullet": False, "is_sinker": True},
            sources=[{"id": "supabase-bond_identity", "kind": "issuer_disclosure"}],
        )
        # Day count is unresolved → no tier hashes published, status=unknown,
        # where_to_find populated.
        assert record["canonical_field_status"]["day_count"] == "unknown"
        assert "day_count" in record["where_to_find"]
        assert record["tier_hashes"] == {}

    def test_two_digit_years_pivot_per_field(self):
        # maturity_date 2-digit year is forward-pivoted; issue_date and
        # first_coupon_date are backward-pivoted. With asof=2026-05-10:
        #   maturity '60' → 2060 (forward)
        #   issue    '20' → 2020 (backward)
        #   first    '21' → 2021 (backward)
        record = normalize_to_published_record(
            raw_row={
                "coupon": 3.87,
                "maturity_date": "23-Jul-60",
                "frequency": 2,
                "day_count": "BOND_BASIS_30_360",
                "issue_date": "30-Sep-20",
                "first_coupon_date": "23-Jan-21",
            },
            isin=PANAMA_ISIN,
            asof=date(2026, 5, 10),
            structural_flags={"is_bullet": False, "is_sinker": True},
            sources=[{"id": "vendor-feed", "kind": "vendor"}],
        )
        canonical = normalize_to_published_record(
            raw_row={
                "coupon": 3.87,
                "maturity_date": "2060-07-23",
                "frequency": 2,
                "day_count": "BOND_BASIS_30_360",
                "issue_date": "2020-09-30",
                "first_coupon_date": "2021-01-23",
            },
            isin=PANAMA_ISIN,
            asof=date(2026, 5, 10),
            structural_flags={"is_bullet": False, "is_sinker": True},
            sources=[{"id": "vendor-feed", "kind": "vendor"}],
        )
        assert record["tier_hashes"] == canonical["tier_hashes"]

    def test_vendor_shaped_row_normalises_dates_freq_calendar_bdc(self):
        # Everything ambiguous-but-resolvable: textual date, "Semi", BDC and
        # calendar shorthands. Must produce a complete record.
        record = normalize_to_published_record(
            raw_row={
                "coupon": "3.87%",
                "maturity_date": "23-Jul-2060",
                "frequency": "Semi-Annual",
                "day_count": "BOND_BASIS_30_360",
                "issue_date": 44104,  # 2020-09-30 as Excel serial
                "first_coupon_date": "January 23, 2021",
                "calendar": "NYC",
                "business_day_convention": "MF",
            },
            isin=PANAMA_ISIN,
            asof=date(2026, 5, 10),
            structural_flags={"is_bullet": False, "is_sinker": True},
            sources=[{"id": "vendor-feed", "kind": "vendor"}],
        )
        assert record["canonical_field_status"]["maturity_date"] == "explicit"
        assert record["canonical_field_status"]["calendar"] == "explicit"
        assert record["canonical_field_status"]["business_day_convention"] == "explicit"
        assert record["tier_hashes"]["calc_hash_min"].startswith("sha256:")

    def test_vendor_shaped_row_matches_canonical_input_hash(self):
        # The vendor-shaped row and the equivalent canonical row must produce
        # byte-identical tier hashes — that is the whole point of the adapter.
        vendor = normalize_to_published_record(
            raw_row={
                "coupon": "3.87",
                "maturity_date": "23-Jul-2060",
                "frequency": "S",
                "day_count": "BOND_BASIS_30_360",
                "issue_date": "30-Sep-2020",
                "first_coupon_date": "23-Jan-2021",
            },
            isin=PANAMA_ISIN,
            asof=date(2026, 5, 10),
            structural_flags={"is_bullet": False, "is_sinker": True},
            sources=[{"id": "vendor-feed", "kind": "vendor"}],
        )
        canonical = normalize_to_published_record(
            raw_row={
                "coupon": 3.87,
                "maturity_date": "2060-07-23",
                "frequency": 2,
                "day_count": "BOND_BASIS_30_360",
                "issue_date": "2020-09-30",
                "first_coupon_date": "2021-01-23",
            },
            isin=PANAMA_ISIN,
            asof=date(2026, 5, 10),
            structural_flags={"is_bullet": False, "is_sinker": True},
            sources=[{"id": "vendor-feed", "kind": "vendor"}],
        )
        assert vendor["tier_hashes"] == canonical["tier_hashes"]

    def test_ambiguous_numeric_date_raises(self):
        with pytest.raises(ValueError, match="ambiguous"):
            normalize_to_published_record(
                raw_row={
                    "coupon": 3.87,
                    "maturity_date": "10/05/2026",  # DD/MM vs MM/DD
                    "frequency": 2,
                    "day_count": "BOND_BASIS_30_360",
                },
                isin=PANAMA_ISIN,
                asof=date(2026, 5, 10),
                structural_flags={"is_bullet": True},
                sources=[{"id": "vendor-feed", "kind": "vendor"}],
            )

    def test_fractional_coupon_raises_without_opt_in(self):
        with pytest.raises(ValueError, match="fraction"):
            normalize_to_published_record(
                raw_row={
                    "coupon": 0.0387,  # plausibly meant 3.87%
                    "maturity_date": "2060-07-23",
                    "frequency": 2,
                    "day_count": "BOND_BASIS_30_360",
                },
                isin=PANAMA_ISIN,
                asof=date(2026, 5, 10),
                structural_flags={"is_bullet": True},
                sources=[{"id": "vendor-feed", "kind": "vendor"}],
            )

    def test_panama_resolves_via_prospectus_phrase(self):
        record = normalize_to_published_record(
            raw_row={
                "coupon": 3.87,
                "maturity_date": "2060-07-23",
                "frequency": 2,
                "day_count": "30/360",  # ambiguous
                "issue_date": "2020-09-30",
                "first_coupon_date": "2021-01-23",
            },
            isin=PANAMA_ISIN,
            asof=date(2026, 5, 10),
            structural_flags={"is_bullet": False, "is_sinker": True},
            sources=[{"id": "EDGAR-424B5-0001193125-20-252589",
                       "kind": "prospectus"}],
            prospectus_text=(
                "computed on the basis of a 360-day year consisting of "
                "twelve 30-day months"
            ),
        )
        # Resolved → tier hashes appear, status explicit.
        assert record["canonical_field_status"]["day_count"] == "explicit"
        assert record["tier_hashes"]["calc_hash_min"].startswith("sha256:")
        assert "day_count" not in record.get("where_to_find", {})


# -------- JSON Schema conformance --------

@pytest.fixture(scope="module")
def registry():
    pytest.importorskip("jsonschema")
    pytest.importorskip("referencing")
    from referencing import Registry, Resource
    reg = Registry()
    for path in SCHEMA_DIR.glob("*.schema.json"):
        contents = json.loads(path.read_text())
        resource = Resource.from_contents(contents)
        reg = reg.with_resource(uri=contents["$id"], resource=resource)
        reg = reg.with_resource(uri=path.name, resource=resource)
    return reg


def test_adapter_output_conforms_to_published_record_schema(registry):
    pytest.importorskip("jsonschema")
    from jsonschema import Draft202012Validator
    record = normalize_to_published_record(
        raw_row={
            "coupon": 3.87,
            "maturity_date": "2060-07-23",
            "frequency": 2,
            "day_count": "BOND_BASIS_30_360",
            "issue_date": "2020-09-30",
            "first_coupon_date": "2021-01-23",
        },
        isin=PANAMA_ISIN,
        asof=date(2026, 5, 10),
        structural_flags={
            "is_bullet": False, "is_sinker": True, "is_amortizing": False,
            "is_callable": False, "is_putable": False, "is_floater": False,
            "is_step_up": False, "is_step_down": False,
            "has_make_whole": False, "is_zero_coupon": False,
        },
        sources=[{
            "id": "EDGAR-424B5-0001193125-20-252589",
            "kind": "prospectus",
            "url": "https://www.sec.gov/Archives/edgar/data/76027/000119312520252589/d83953d424b5.htm",
            "asof": "2020-09-24",
        }],
    )
    schema = json.loads((SCHEMA_DIR / "published_record.schema.json").read_text())
    Draft202012Validator(schema, registry=registry).validate(record)
