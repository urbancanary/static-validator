"""Tests for the MCP tool functions.

The tools are imported and called directly (not via the MCP transport) so
the tests don't need a running server. The transport layer is the official
mcp package's responsibility, not ours.
"""

from __future__ import annotations

import pytest

from static_validator_mcp.data_provider import known_isins
from static_validator_mcp.server import (
    fetch_canonical_record_impl as fetch_canonical_record,
    list_known_isins_impl as list_known_isins,
    validate_bond_static_impl as validate_bond_static,
)

PANAMA = "US698299BL70"
PANAMA_BOND = {
    "coupon": 3.87,
    "maturity_date": "2060-07-23",
    "frequency": 2,
    "day_count": "BOND_BASIS_30_360",
    "issue_date": "2020-09-30",
    "first_coupon_date": "2021-01-23",
}


class TestListKnownIsins:
    def test_panama_present(self):
        result = list_known_isins()
        assert PANAMA in result["isins"]
        assert result["count"] >= 1
        assert result["schema_version"] == "0.1"


class TestFetchCanonicalRecord:
    def test_panama_returns_record(self):
        record = fetch_canonical_record(PANAMA)
        assert record["isin"] == PANAMA
        assert "tier_hashes" in record
        assert "structural_flags" in record
        assert record["structural_flags"]["is_sinker"] is True

    def test_unknown_isin_returns_error(self):
        record = fetch_canonical_record("US000000AA09")
        assert "error" in record
        assert "known_isins" in record


class TestValidateBondStatic:
    def test_correct_bond_matches(self):
        result = validate_bond_static(PANAMA, PANAMA_BOND)
        assert result["match"] is True
        assert result["tier_used"] == "calc_hash_full"
        # Sinker warning must surface so the caller knows about the
        # structural complexity even when static matches.
        assert any("sinker" in w for w in result["warnings"])

    def test_wrong_day_count_mismatches(self):
        wrong = dict(PANAMA_BOND, day_count="ISMA_30_360")
        result = validate_bond_static(PANAMA, wrong)
        assert result["match"] is False
        assert "day_count" in result["mismatched_fields"]

    def test_min_only_matches_min_tier(self):
        client = {
            "coupon": 3.87,
            "maturity_date": "2060-07-23",
            "frequency": 2,
            "day_count": "BOND_BASIS_30_360",
        }
        result = validate_bond_static(PANAMA, client)
        # Min-tier hash matches even without explicit dates; std/full tiers
        # diverge because derivation can't reproduce the prospectus dates.
        assert result["client_hashes"]["calc_hash_min"] == result["canonical_hashes"]["calc_hash_min"]
        assert result["match"] is False  # std/full don't match
        # The user is told where to find the missing fields.
        assert "where_to_find" in result

    def test_unknown_isin_returns_error(self):
        result = validate_bond_static("US000000AA09", PANAMA_BOND)
        assert "error" in result

    def test_invalid_bond_data_returns_error(self):
        bad = {"coupon": "not a number"}  # missing required fields
        result = validate_bond_static(PANAMA, bad)
        assert "error" in result
