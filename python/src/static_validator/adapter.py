"""Normalization adapter (Layer A).

Takes raw, possibly-ambiguous vendor-shaped bond static plus multi-source
observations, and produces a wire-format ``PublishedRecord`` conforming to
``schema/published_record.schema.json``.

Layer A is pure: no IO, no DB calls, no scraping. Given identical inputs it
produces identical outputs in every language / runtime. The Python
implementation here is the reference; a JS/Rust port would mirror it
behaviourally.

Layer B (the pipeline that actually pulls bond_identity rows + multi-source
data and feeds them through this layer) lives in ``etf-scraper`` and is
deliberately kept separate.

Resolution policy (per design conversation 2026-05-10, conservative):

- A field is resolved with **high** confidence when:
  - the raw value is already a canonical enum, OR
  - 3+ independent sources (raw + observations + prospectus) agree on the
    same canonical enum, OR
  - the prospectus text contains a phrase that definitively maps to a
    single canonical enum.
- A field is resolved with **medium** confidence when 2 sources agree.
- A field is **unresolved** otherwise.

ISIN-prefix heuristics (US/USP/XS) are recorded in the reasoning trace as
*hints* but never tip resolution. They exist so a downstream reviewer can
prioritise which unresolved bonds to investigate first.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from .canonicalize import (
    BDC_ENUM,
    CALENDAR_ENUM,
    DAY_COUNT_ENUM,
    _AMBIGUOUS_DAY_COUNT_HINTS,
)
from .derivations import DEFAULT_BDC, DEFAULT_CALENDAR, apply_derivations
from .hashes import compute_all_tiers
from .wire import (
    Confidence,
    FieldStatus,
    PublishedRecord,
    SourceReference,
    StructuralFlags,
    WhereToFind,
)


Confidence4 = Literal["high", "medium", "low", "unresolved"]


@dataclass
class FieldResolution:
    """The outcome of disambiguating one field."""

    canonical: str | None
    confidence: Confidence4
    field_status: FieldStatus
    reasoning: list[str] = field(default_factory=list)
    sources_used: list[str] = field(default_factory=list)


# ---- ISIN-prefix hint table (informational signal only) ----

_DAY_COUNT_HINTS_BY_PREFIX: dict[str, str] = {
    # US-prefix: many USD sovereign / agency / corporate issues use BOND_BASIS.
    # Heuristic only — lots of US-prefix bonds are ACT_ACT_ISDA (treasuries).
    "US": "BOND_BASIS_30_360",
    "USP": "BOND_BASIS_30_360",
    # XS-prefix Eurobonds: typically ISMA_30_360 or ACT_ACT_ICMA.
    "XS": "ISMA_30_360",
}


def _isin_prefix(isin: str) -> str:
    if isin.startswith("USP") or isin.startswith("USY"):
        return "USP"
    return isin[:2]


def _isin_hint_for_day_count(isin: str) -> str | None:
    return _DAY_COUNT_HINTS_BY_PREFIX.get(_isin_prefix(isin))


# ---- Prospectus-text matchers ----

# Each entry: (regex, canonical_enum, why). Matched against lowercased
# prospectus text. Order matters — more specific patterns first.
_PROSPECTUS_DAY_COUNT_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"30e/360\s*\(\s*isma\s*\)"), "ISMA_30_360",
     "prospectus pinpoints '30E/360 (ISMA)'"),
    (re.compile(r"30e/360\s*\(\s*isda\s*\)"), "ISDA_30E_360",
     "prospectus pinpoints '30E/360 (ISDA)'"),
    (re.compile(r"eurobond\s+basis"), "ISDA_30E_360",
     "prospectus uses 'Eurobond Basis' phrasing"),
    (re.compile(r"30/360\s*\(\s*bond\s+basis\s*\)"), "BOND_BASIS_30_360",
     "prospectus pinpoints '30/360 (Bond Basis)'"),
    (re.compile(r"360-day\s+year\s+consisting\s+of\s+twelve\s+30-day\s+months"),
     "BOND_BASIS_30_360",
     "prospectus uses canonical BOND_BASIS phrasing"),
    (re.compile(r"act/act\s*\(\s*icma\s*\)"), "ACT_ACT_ICMA",
     "prospectus pinpoints 'ACT/ACT (ICMA)'"),
    (re.compile(r"act/act\s*\(\s*isda\s*\)"), "ACT_ACT_ISDA",
     "prospectus pinpoints 'ACT/ACT (ISDA)'"),
    (re.compile(r"actual/365\s*\(\s*fixed\s*\)"), "ACT_365_FIXED",
     "prospectus pinpoints 'Actual/365 (Fixed)'"),
]


def _prospectus_match(prospectus_text: str) -> tuple[str, str] | None:
    """Return (canonical_enum, reasoning) if the text contains a definitive
    phrase, else None."""
    lower = prospectus_text.lower()
    for pattern, enum_value, why in _PROSPECTUS_DAY_COUNT_PATTERNS:
        if pattern.search(lower):
            return enum_value, why
    return None


# ---- Disambiguators ----

def _is_canonical(value: str | None, enum_set: frozenset[str]) -> bool:
    return isinstance(value, str) and value in enum_set


def disambiguate_day_count(
    raw: str | None,
    isin: str,
    observations: dict[str, str] | None = None,
    prospectus_text: str | None = None,
) -> FieldResolution:
    """Resolve a possibly-ambiguous day_count value to a canonical enum.

    Args:
        raw: the value carried on the primary record (e.g. bond_identity row).
            May be None, a canonical enum, an ambiguous shorthand, or junk.
        isin: the bond's ISIN. Used only for ISIN-prefix hint reasoning.
        observations: ``{source_id: raw_value}`` from independent sources
            (other ETF holding files, CBonds, Markit, etc.).
        prospectus_text: optional excerpt from the issuer's prospectus.

    Conservative resolution: never picks among ambiguous alternatives unless
    multiple sources agree or the prospectus disambiguates definitively.
    """
    observations = dict(observations or {})
    reasoning: list[str] = []
    sources_used: list[str] = []

    # 1. Prospectus first — if it pins the answer, that overrides everything.
    if prospectus_text:
        match = _prospectus_match(prospectus_text)
        if match is not None:
            enum_value, why = match
            reasoning.append(why)
            sources_used.append("prospectus")
            return FieldResolution(
                canonical=enum_value,
                confidence="high",
                field_status="explicit",
                reasoning=reasoning,
                sources_used=sources_used,
            )

    # 2. Raw is already canonical — accept, but check observations don't
    #    contradict.
    candidate_values: list[tuple[str, str]] = []  # (source_id, canonical_enum)
    if _is_canonical(raw, DAY_COUNT_ENUM):
        candidate_values.append(("primary", raw))  # type: ignore[arg-type]

    # 3. Pull canonical observations into the candidate set.
    for source_id, value in observations.items():
        if _is_canonical(value, DAY_COUNT_ENUM):
            candidate_values.append((source_id, value))

    if candidate_values:
        counts = Counter(v for _, v in candidate_values)
        top_value, top_count = counts.most_common(1)[0]
        agreeing_sources = [s for s, v in candidate_values if v == top_value]
        if top_count >= 3:
            reasoning.append(f"3+ canonical sources agree on {top_value!r}")
            sources_used.extend(agreeing_sources)
            return FieldResolution(
                canonical=top_value, confidence="high", field_status="explicit",
                reasoning=reasoning, sources_used=sources_used,
            )
        if top_count == 2:
            reasoning.append(f"2 canonical sources agree on {top_value!r}")
            sources_used.extend(agreeing_sources)
            hint = _isin_hint_for_day_count(isin)
            if hint:
                reasoning.append(f"ISIN-prefix hint: {hint} (informational)")
            return FieldResolution(
                canonical=top_value, confidence="medium", field_status="explicit",
                reasoning=reasoning, sources_used=sources_used,
            )
        if top_count == 1 and len(set(v for _, v in candidate_values)) == 1:
            # Only one source, only one value, no contradiction.
            reasoning.append(f"single canonical source: {top_value!r}")
            sources_used.extend(agreeing_sources)
            return FieldResolution(
                canonical=top_value, confidence="low", field_status="explicit",
                reasoning=reasoning, sources_used=sources_used,
            )
        # Multiple distinct canonical values present and none has plurality.
        distinct = sorted(counts.keys())
        reasoning.append(
            f"sources disagree across canonical values {distinct}; "
            "manual review required"
        )
        hint = _isin_hint_for_day_count(isin)
        if hint:
            reasoning.append(f"ISIN-prefix hint: {hint} (informational)")
        return FieldResolution(
            canonical=None, confidence="unresolved", field_status="unknown",
            reasoning=reasoning, sources_used=[s for s, _ in candidate_values],
        )

    # 4. No canonical sources. Inspect the raw value for the ambiguity hint.
    raw_upper = raw.upper().strip() if isinstance(raw, str) else None
    if raw_upper in _AMBIGUOUS_DAY_COUNT_HINTS:
        candidates = _AMBIGUOUS_DAY_COUNT_HINTS[raw_upper]
        reasoning.append(
            f"primary value {raw!r} is ambiguous; possible canonical forms: "
            f"{', '.join(candidates)}"
        )
    elif raw is None:
        reasoning.append("primary record has no day_count value")
    else:
        reasoning.append(f"primary value {raw!r} is not a recognised canonical or ambiguous form")

    # ISIN hint as informational signal.
    hint = _isin_hint_for_day_count(isin)
    if hint:
        reasoning.append(
            f"ISIN-prefix hint: {hint} (informational only; not used to resolve)"
        )

    return FieldResolution(
        canonical=None, confidence="unresolved", field_status="unknown",
        reasoning=reasoning, sources_used=[],
    )


def _disambiguate_simple_enum(
    raw: str | None,
    enum_set: frozenset[str],
    default_value: str,
    observations: dict[str, str] | None = None,
) -> FieldResolution:
    """Used for calendar and BDC where there is no equivalent of '30/360'
    ambiguity — the field is either canonical, defaulted, or unknown.
    """
    observations = dict(observations or {})
    reasoning: list[str] = []
    sources_used: list[str] = []

    if _is_canonical(raw, enum_set):
        canonical_obs = [(s, v) for s, v in observations.items() if _is_canonical(v, enum_set)]
        agree = sum(1 for _, v in canonical_obs if v == raw)
        if agree >= 2:
            reasoning.append(f"primary value {raw!r} confirmed by {agree} observation(s)")
            sources_used = ["primary"] + [s for s, v in canonical_obs if v == raw]
            return FieldResolution(raw, "high", "explicit", reasoning, sources_used)
        reasoning.append(f"primary value {raw!r} accepted (single source)")
        return FieldResolution(raw, "low", "explicit", reasoning, ["primary"])

    if raw is None:
        reasoning.append(
            f"primary record has no value; canonical default {default_value!r} applied"
        )
        return FieldResolution(default_value, "high", "default", reasoning, [])

    reasoning.append(
        f"primary value {raw!r} is not a recognised canonical enum; "
        f"left unresolved (consider sourcing from prospectus)"
    )
    return FieldResolution(None, "unresolved", "unknown", reasoning, [])


def disambiguate_calendar(
    raw: str | None,
    isin: str,
    observations: dict[str, str] | None = None,
) -> FieldResolution:
    return _disambiguate_simple_enum(raw, CALENDAR_ENUM, DEFAULT_CALENDAR, observations)


def disambiguate_bdc(
    raw: str | None,
    isin: str,
    observations: dict[str, str] | None = None,
) -> FieldResolution:
    return _disambiguate_simple_enum(raw, BDC_ENUM, DEFAULT_BDC, observations)


# ---- Top-level adapter ----

def _aggregate_confidence(resolutions: list[FieldResolution]) -> Confidence:
    """Roll per-field confidences into a single record-level confidence per
    SCHEMA.md (high/medium/low). 'unresolved' downgrades to 'low' for the
    purpose of the published record.
    """
    levels = {r.confidence for r in resolutions}
    if "unresolved" in levels or "low" in levels:
        return "low"
    if "medium" in levels:
        return "medium"
    return "high"


def normalize_to_published_record(
    raw_row: dict[str, Any],
    *,
    isin: str,
    asof: date,
    structural_flags: StructuralFlags,
    sources: list[SourceReference],
    observations: dict[str, dict[str, str]] | None = None,
    prospectus_text: str | None = None,
) -> PublishedRecord:
    """Build a wire-format ``PublishedRecord`` from a raw bond_identity-shaped
    row plus optional multi-source observations.

    Args:
        raw_row: flat dict carrying coupon, day_count, frequency, maturity_date,
            optionally issue_date, first_coupon_date, calendar, BDC. Values
            may be None or may be ambiguous vendor strings.
        isin: bond ISIN.
        asof: snapshot date for this canonical record.
        structural_flags: structural metadata to publish alongside (must
            include is_bullet at minimum per the schema).
        sources: at least one SourceReference for the published record.
        observations: ``{source_id: {field_name: raw_value}}`` from
            independent sources (other ETF holdings, CBonds, etc.).
        prospectus_text: optional excerpt of issuer prospectus, used for
            high-confidence day_count disambiguation.

    Returns a record conforming to ``schema/published_record.schema.json``.
    Tier hashes are computed only for tiers whose field set is fully
    resolved (or derivable). Unresolved fields are flagged in
    ``canonical_field_status`` and ``where_to_find``.
    """
    observations = observations or {}

    # Pull per-field observations for each disambiguator.
    def _obs_for(field_name: str) -> dict[str, str]:
        return {
            sid: vals[field_name]
            for sid, vals in observations.items()
            if field_name in vals and vals[field_name] is not None
        }

    day_count_res = disambiguate_day_count(
        raw_row.get("day_count"), isin,
        observations=_obs_for("day_count"),
        prospectus_text=prospectus_text,
    )
    calendar_res = disambiguate_calendar(
        raw_row.get("calendar"), isin, observations=_obs_for("calendar"),
    )
    bdc_res = disambiguate_bdc(
        raw_row.get("business_day_convention"), isin,
        observations=_obs_for("business_day_convention"),
    )

    # Build the canonical record for hashing. Only include resolved fields.
    canonical_record: dict[str, Any] = {"isin": isin}
    field_status: dict[str, FieldStatus] = {}
    where_to_find: WhereToFind = {}

    # Mandatory pass-throughs (let canonicalize_record validate types/format).
    for field_name in ("coupon", "maturity_date", "frequency"):
        if field_name not in raw_row or raw_row[field_name] is None:
            raise ValueError(f"raw_row is missing mandatory field {field_name!r}")
        canonical_record[field_name] = raw_row[field_name]
        field_status[field_name] = "explicit"

    # day_count via the resolver.
    if day_count_res.canonical is not None:
        canonical_record["day_count"] = day_count_res.canonical
        field_status["day_count"] = day_count_res.field_status
    else:
        field_status["day_count"] = "unknown"
        where_to_find["day_count"] = [
            {"id": "issuer-prospectus", "kind": "prospectus",
             "note": "; ".join(day_count_res.reasoning)}
        ]

    # Optional dates: pass through if present, otherwise mark as derived
    # (apply_derivations will fill them at hash time).
    for field_name in ("issue_date", "first_coupon_date"):
        v = raw_row.get(field_name)
        if v is not None:
            canonical_record[field_name] = v
            field_status[field_name] = "explicit"
        else:
            field_status[field_name] = "derived"

    # Calendar / BDC.
    for field_name, res in (("calendar", calendar_res),
                            ("business_day_convention", bdc_res)):
        if res.canonical is not None:
            canonical_record[field_name] = res.canonical
            field_status[field_name] = res.field_status
        else:
            field_status[field_name] = "unknown"
            where_to_find[field_name] = [
                {"id": "issuer-prospectus", "kind": "prospectus",
                 "note": "; ".join(res.reasoning)}
            ]

    # Compute tier hashes — only for tiers whose required fields are present
    # in the canonical_record (after applying derivations).
    tier_hashes: dict[str, str] = {}
    if "day_count" in canonical_record:
        try:
            derived = apply_derivations(canonical_record)
            tier_hashes = compute_all_tiers(derived)
        except (ValueError, TypeError):
            # If hashing blows up (e.g. zero-coupon edge cases), leave hashes
            # absent and let the consumer see canonical_field_status to
            # understand why.
            tier_hashes = {}

    confidence = _aggregate_confidence([day_count_res, calendar_res, bdc_res])

    record: PublishedRecord = {
        "isin": isin,
        "schema_version": "0.1",
        "asof": asof.isoformat(),
        "tier_hashes": tier_hashes,
        "structural_flags": structural_flags,
        "canonical_field_status": field_status,
        "confidence": confidence,
        "sources": sources,
    }
    if where_to_find:
        record["where_to_find"] = where_to_find

    return record


__all__ = [
    "FieldResolution",
    "disambiguate_day_count",
    "disambiguate_calendar",
    "disambiguate_bdc",
    "normalize_to_published_record",
]
