"""High-level validate() API.

Compares a client's local bond static against published canonical hashes,
using the highest tier the client has full data for. Reports which fields
disagree when the hashes mismatch, and surfaces any structural flags from
the published record so the caller knows when special handling is required
downstream (sinker schedule, callable yield-to-worst, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .canonicalize import canonicalize_record
from .derivations import apply_derivations
from .hashes import ALL_TIERS, TierName, _TIER_FIELDS, compute_tier_hash


@dataclass
class ValidationResult:
    """Outcome of comparing client static against published canonical hashes."""

    isin: str
    match: bool
    tier_used: TierName | None
    mismatched_fields: list[str]
    client_hashes: dict[TierName, str]
    canonical_hashes: dict[TierName, str]
    structural_flags: dict[str, bool] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    note: str = ""


def _highest_tier_available(record: dict[str, Any]) -> TierName | None:
    derived = apply_derivations(record)
    for tier in reversed(ALL_TIERS):
        if all(f in derived for f in _TIER_FIELDS[tier]):
            return tier
    return None


_FLAG_WARNINGS: dict[str, str] = {
    "is_sinker": "bond is a sinker — your engine must apply the sinker schedule or pricing will be wrong in late years",
    "is_amortizing": "bond is amortizing — principal repays before maturity; bullet-mode pricing will be wrong",
    "is_callable": "bond is callable — use yield-to-worst, not yield-to-maturity, for risk metrics",
    "is_putable": "bond is putable — holder may exercise before maturity",
    "is_floater": "bond is a floater — coupon resets against an index; the published coupon is the current fixing only",
    "is_step_up": "bond has a step-up coupon schedule — the coupon field captures only one rate",
    "is_step_down": "bond has a step-down coupon schedule — the coupon field captures only one rate",
}


def _warnings_for_flags(flags: dict[str, bool]) -> list[str]:
    return [msg for flag, msg in _FLAG_WARNINGS.items() if flags.get(flag) is True]


def validate_bond_static(
    record: dict[str, Any],
    published: dict[str, Any] | dict[TierName, str],
) -> ValidationResult:
    """Compare client's static against the canonical record.

    ``record`` is the client's local static (mandatory fields plus whatever
    optional fields they have). ``published`` is either:

      a) The full published record from the read API:
         {"tier_hashes": {...}, "structural_flags": {...}, ...}
      b) A bare ``{tier_name: hash}`` dict (legacy shape; structural flags
         and warnings will be empty in the result).

    Picks the highest tier the client has data for and that is also in the
    published hashes. Computes the client's hash at that tier and compares.
    On mismatch, identifies WHICH tier first diverges and which fields are
    introduced at that tier. Surfaces structural flags from the published
    record so callers know when special downstream handling is needed.
    """
    canonical_hashes, structural_flags = _unpack_published(published)

    normalized = canonicalize_record(record)
    derived = apply_derivations(normalized)

    client_hashes: dict[TierName, str] = {}
    for tier in ALL_TIERS:
        try:
            client_hashes[tier] = compute_tier_hash(derived, tier, derive=False)
        except ValueError:
            continue

    common_tiers = [t for t in ALL_TIERS if t in client_hashes and t in canonical_hashes]
    warnings = _warnings_for_flags(structural_flags)

    if not common_tiers:
        return ValidationResult(
            isin=normalized["isin"],
            match=False,
            tier_used=None,
            mismatched_fields=[],
            client_hashes=client_hashes,
            canonical_hashes=canonical_hashes,
            structural_flags=structural_flags,
            warnings=warnings,
            note="no common tier between client data and canonical hashes",
        )

    highest_tier = common_tiers[-1]
    if client_hashes[highest_tier] == canonical_hashes[highest_tier]:
        return ValidationResult(
            isin=normalized["isin"],
            match=True,
            tier_used=highest_tier,
            mismatched_fields=[],
            client_hashes=client_hashes,
            canonical_hashes=canonical_hashes,
            structural_flags=structural_flags,
            warnings=warnings,
        )

    # Mismatch — narrow down by checking lower tiers in order, identifying
    # which fields are introduced at the first failing tier.
    first_failing_tier: TierName = highest_tier
    for tier in common_tiers:
        if client_hashes[tier] != canonical_hashes[tier]:
            first_failing_tier = tier
            break

    introduced_at_failing = _TIER_FIELDS[first_failing_tier]
    if first_failing_tier != ALL_TIERS[0]:
        prev_idx = ALL_TIERS.index(first_failing_tier) - 1
        prev_fields = set(_TIER_FIELDS[ALL_TIERS[prev_idx]])
        introduced_at_failing = tuple(f for f in _TIER_FIELDS[first_failing_tier] if f not in prev_fields)

    return ValidationResult(
        isin=normalized["isin"],
        match=False,
        tier_used=highest_tier,
        mismatched_fields=list(introduced_at_failing),
        client_hashes=client_hashes,
        canonical_hashes=canonical_hashes,
        structural_flags=structural_flags,
        warnings=warnings,
        note=f"first divergence at tier {first_failing_tier}",
    )


def _unpack_published(
    published: dict[str, Any] | dict[TierName, str],
) -> tuple[dict[TierName, str], dict[str, bool]]:
    """Accept either the full published-record shape or the bare hashes dict."""
    if "tier_hashes" in published:
        hashes = dict(published["tier_hashes"])
        flags = dict(published.get("structural_flags") or {})
        return hashes, flags
    # Legacy: caller passed bare {tier_name: hash}.
    return dict(published), {}
