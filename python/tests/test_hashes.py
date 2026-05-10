"""Hash tier tests + golden fixture verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from static_validator.canonicalize import canonicalize_json
from static_validator.derivations import apply_derivations
from static_validator.hashes import (
    ALL_TIERS,
    _TIER_FIELDS,
    compute_all_tiers,
    compute_tier_hash,
)

GOLDEN = Path(__file__).parent / "golden"


def _expected_hash_for(record: dict, tier: str) -> str:
    derived = apply_derivations(record)
    fields = _TIER_FIELDS[tier]
    projected = {f: derived[f] for f in fields if f in derived}
    canonical = canonicalize_json(projected)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class TestTierHashShape:
    def test_returns_sha256_prefix(self):
        rec = {
            "isin": "US698299BL70",
            "coupon": 3.87,
            "maturity_date": "2060-07-23",
            "frequency": 2,
            "day_count": "BOND_BASIS_30_360",
        }
        h = compute_tier_hash(rec, "calc_hash_min")
        assert h.startswith("sha256:")
        assert len(h) == len("sha256:") + 64


class TestTierHashDeterminism:
    def test_same_input_same_hash(self):
        rec = {
            "isin": "US698299BL70",
            "coupon": 3.87,
            "maturity_date": "2060-07-23",
            "frequency": 2,
            "day_count": "BOND_BASIS_30_360",
        }
        h1 = compute_tier_hash(rec, "calc_hash_min")
        h2 = compute_tier_hash(rec, "calc_hash_min")
        assert h1 == h2

    def test_equivalent_inputs_same_hash(self):
        # Reordered keys, decimal-vs-string coupon — same logical input.
        a = {
            "isin": "US698299BL70",
            "coupon": 3.87,
            "maturity_date": "2060-07-23",
            "frequency": 2,
            "day_count": "BOND_BASIS_30_360",
        }
        b = {
            "day_count": "BOND_BASIS_30_360",
            "frequency": 2,
            "coupon": "3.870000",
            "maturity_date": "2060-07-23",
            "isin": "US698299BL70",
        }
        for tier in ALL_TIERS:
            try:
                ha = compute_tier_hash(a, tier)
                hb = compute_tier_hash(b, tier)
                assert ha == hb, f"mismatch at tier {tier}"
            except ValueError:
                # Tier requires fields not present — skip.
                continue


class TestTierHashSensitivity:
    def test_different_coupon_different_hash(self):
        base = {
            "isin": "US698299BL70",
            "coupon": 3.87,
            "maturity_date": "2060-07-23",
            "frequency": 2,
            "day_count": "BOND_BASIS_30_360",
        }
        wrong = dict(base, coupon=3.88)
        assert compute_tier_hash(base, "calc_hash_min") != compute_tier_hash(
            wrong, "calc_hash_min"
        )

    def test_different_day_count_different_hash(self):
        base = {
            "isin": "US698299BL70",
            "coupon": 3.87,
            "maturity_date": "2060-07-23",
            "frequency": 2,
            "day_count": "BOND_BASIS_30_360",
        }
        # The actual WNBF correction case from memory 260: ISMA vs Bond Basis.
        wrong = dict(base, day_count="ISMA_30_360")
        assert compute_tier_hash(base, "calc_hash_min") != compute_tier_hash(
            wrong, "calc_hash_min"
        )


class TestComputeAllTiers:
    def test_full_record_returns_three_tiers(self):
        rec = json.loads((GOLDEN / "panama_2060.input.json").read_text())
        all_tiers = compute_all_tiers(rec)
        assert set(all_tiers.keys()) == set(ALL_TIERS)

    def test_min_only_when_optional_missing(self):
        # Zero-coupon with no first_coupon_date → cannot derive optional
        # dates, so std and full tiers are unavailable.
        rec = {
            "isin": "US912828YY08",
            "coupon": 0,
            "maturity_date": "2030-01-15",
            "frequency": 0,
            "day_count": "ACT_ACT_ICMA",
        }
        all_tiers = compute_all_tiers(rec)
        assert "calc_hash_min" in all_tiers
        assert "calc_hash_std" not in all_tiers


class TestPanamaGolden:
    """Lock the canonical hashes for PANAMA 2060 against the published
    expected.json fixture. If this test fails after a code change, the
    schema has shifted and a MAJOR version bump is needed.
    """

    def setup_method(self):
        self.record = json.loads((GOLDEN / "panama_2060.input.json").read_text())
        self.expected = json.loads((GOLDEN / "panama_2060.expected.json").read_text())

    def test_min_hash_locked(self):
        h = compute_tier_hash(self.record, "calc_hash_min")
        assert h == self.expected["tier_hashes"]["calc_hash_min"]

    def test_std_hash_locked(self):
        h = compute_tier_hash(self.record, "calc_hash_std")
        assert h == self.expected["tier_hashes"]["calc_hash_std"]

    def test_full_hash_locked(self):
        h = compute_tier_hash(self.record, "calc_hash_full")
        assert h == self.expected["tier_hashes"]["calc_hash_full"]
