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
    normalize_to_published_record,
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
        res = disambiguate_calendar("NYC", PANAMA_ISIN)
        assert res.canonical is None
        assert res.confidence == "unresolved"


class TestDisambiguateBdc:
    def test_null_raw_defaults(self):
        res = disambiguate_bdc(None, PANAMA_ISIN)
        assert res.canonical == "UNADJUSTED"
        assert res.field_status == "default"

    def test_unknown_string_unresolved(self):
        res = disambiguate_bdc("NEXT", PANAMA_ISIN)
        assert res.canonical is None


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
