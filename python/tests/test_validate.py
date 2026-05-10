"""High-level validate() API tests."""

from __future__ import annotations

import json
from pathlib import Path

from static_validator.hashes import compute_all_tiers
from static_validator.validate import validate_bond_static

GOLDEN = Path(__file__).parent / "golden"


PANAMA = {
    "isin": "US698299BL70",
    "coupon": 3.87,
    "maturity_date": "2060-07-23",
    "frequency": 2,
    "day_count": "BOND_BASIS_30_360",
    "issue_date": "2020-09-30",
    "first_coupon_date": "2021-01-23",
}


class TestValidateMatch:
    def test_perfect_match(self):
        canonical = compute_all_tiers(PANAMA)
        result = validate_bond_static(PANAMA, canonical)
        assert result.match is True
        assert result.tier_used == "calc_hash_full"
        assert result.mismatched_fields == []

    def test_min_only_client_matches_min_tier(self):
        # Client without issue_date / first_coupon_date matches the canonical
        # record at the min tier (which omits those fields), but NOT at std
        # or full — because the derived dates won't equal the prospectus's
        # explicit dates, and that's the point: the client should be told
        # they need to source those fields to validate at higher tiers.
        canonical = compute_all_tiers(PANAMA)
        client = {
            "isin": "US698299BL70",
            "coupon": 3.87,
            "maturity_date": "2060-07-23",
            "frequency": 2,
            "day_count": "BOND_BASIS_30_360",
        }
        result = validate_bond_static(client, canonical)
        # Hashes match at min tier.
        assert result.client_hashes["calc_hash_min"] == canonical["calc_hash_min"]
        # But the high-water tier (full) diverges because issue_date was derived.
        assert result.match is False
        assert "issue_date" in result.mismatched_fields or "first_coupon_date" in result.mismatched_fields


class TestValidateMismatch:
    def test_wrong_day_count(self):
        # The WNBF Panama correction case in reverse: client has the old
        # ISMA value, canonical (us) has Bond Basis.
        canonical = compute_all_tiers(PANAMA)
        wrong = dict(PANAMA, day_count="ISMA_30_360")
        result = validate_bond_static(wrong, canonical)
        assert result.match is False
        # day_count is in the min tier, so divergence is detected at min.
        assert result.tier_used == "calc_hash_full"
        assert "day_count" in result.mismatched_fields

    def test_wrong_optional_field_only(self):
        canonical = compute_all_tiers(PANAMA)
        # Same min-tier fields, different first_coupon_date.
        wrong = dict(PANAMA, first_coupon_date="2021-07-23")
        result = validate_bond_static(wrong, canonical)
        assert result.match is False
        # min tier should still match (no first_coupon_date in min);
        # std tier introduces the field that diverges.
        assert "first_coupon_date" in result.mismatched_fields


class TestStructuralFlags:
    def test_published_record_shape_surfaces_flags(self):
        # Use the actual published-record golden fixture for PANAMA.
        published = json.loads((GOLDEN / "panama_2060.expected.json").read_text())
        result = validate_bond_static(PANAMA, published)
        assert result.match is True
        assert result.structural_flags["is_sinker"] is True
        assert result.structural_flags["is_bullet"] is False
        # The sinker flag must produce a downstream-handling warning.
        assert any("sinker" in w for w in result.warnings)

    def test_legacy_bare_hashes_dict_still_works(self):
        # Backward-compat: caller passes only {tier: hash}, no flags.
        bare = compute_all_tiers(PANAMA)
        result = validate_bond_static(PANAMA, bare)
        assert result.match is True
        assert result.structural_flags == {}
        assert result.warnings == []

    def test_callable_warning(self):
        bare_hashes = compute_all_tiers(PANAMA)
        published = {
            "tier_hashes": bare_hashes,
            "structural_flags": {"is_bullet": False, "is_callable": True},
        }
        result = validate_bond_static(PANAMA, published)
        assert any("callable" in w for w in result.warnings)
        assert any("yield-to-worst" in w for w in result.warnings)


class TestPublishedRecordPropagation:
    """Confirm sources, confidence, where_to_find, and canonical_field_status
    flow through validate_bond_static into the result, so frontends (Claude
    Desktop MCP and Athena UI) get everything they need to render diagnostics.
    """

    def setup_method(self):
        self.published = json.loads((GOLDEN / "panama_2060.expected.json").read_text())

    def test_sources_propagate(self):
        result = validate_bond_static(PANAMA, self.published)
        assert len(result.sources) == 1
        assert result.sources[0]["kind"] == "prospectus"
        assert "EDGAR" in result.sources[0]["id"]

    def test_confidence_propagates(self):
        result = validate_bond_static(PANAMA, self.published)
        assert result.confidence == "high"

    def test_canonical_field_status_propagates(self):
        result = validate_bond_static(PANAMA, self.published)
        assert result.canonical_field_status["coupon"] == "explicit"
        assert result.canonical_field_status["calendar"] == "default"

    def test_where_to_find_propagates_for_default_fields(self):
        result = validate_bond_static(PANAMA, self.published)
        # The PANAMA record uses default for calendar/BDC; where_to_find
        # gives clients a pointer for both.
        assert "calendar" in result.where_to_find
        assert "business_day_convention" in result.where_to_find
        assert result.where_to_find["calendar"][0]["kind"] == "prospectus"
