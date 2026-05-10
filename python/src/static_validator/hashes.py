"""Tier hash construction per SCHEMA.md §6."""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from .canonicalize import canonicalize_json
from .derivations import apply_derivations

TierName = Literal["calc_hash_min", "calc_hash_std", "calc_hash_full"]

_TIER_FIELDS: dict[TierName, tuple[str, ...]] = {
    "calc_hash_min": ("isin", "coupon", "maturity_date", "frequency", "day_count"),
    "calc_hash_std": (
        "isin",
        "coupon",
        "maturity_date",
        "frequency",
        "day_count",
        "issue_date",
        "first_coupon_date",
    ),
    "calc_hash_full": (
        "isin",
        "coupon",
        "maturity_date",
        "frequency",
        "day_count",
        "issue_date",
        "first_coupon_date",
        "calendar",
        "business_day_convention",
    ),
}

ALL_TIERS: tuple[TierName, ...] = ("calc_hash_min", "calc_hash_std", "calc_hash_full")


def _project(record: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    missing = [f for f in fields if f not in record]
    if missing:
        raise ValueError(f"record is missing required fields for tier: {missing}")
    return {f: record[f] for f in fields}


def compute_tier_hash(record: dict[str, Any], tier: TierName, *, derive: bool = True) -> str:
    """Compute the SHA-256 tier hash for ``record``.

    If ``derive`` is True (default), canonical derivations are applied first.
    Set False only when the caller has already applied derivations.

    Returns a hash string in the form ``"sha256:<64 hex chars>"``.
    """
    base = apply_derivations(record) if derive else record
    projected = _project(base, _TIER_FIELDS[tier])
    canonical = canonicalize_json(projected)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def compute_all_tiers(record: dict[str, Any]) -> dict[TierName, str]:
    """Compute all three tier hashes. Tiers requiring missing fields are
    omitted from the returned dict rather than raising.
    """
    derived = apply_derivations(record)
    out: dict[TierName, str] = {}
    for tier in ALL_TIERS:
        try:
            out[tier] = compute_tier_hash(derived, tier, derive=False)
        except ValueError:
            continue
    return out
