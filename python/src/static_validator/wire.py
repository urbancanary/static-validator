"""TypedDicts mirroring the JSON Schema files in ../schema/.

These types are the single source of truth for the wire format on the Python
side. Both the SDK and any future server implementation should use them. If
the JSON Schema files change, update these in lockstep.

We use TypedDict (stdlib, zero deps) rather than Pydantic to keep the package
dependency-free. Validation against the JSON Schema can be added as an
optional extra later (jsonschema package).
"""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

# ---- reusable building blocks ----

TierName = Literal["calc_hash_min", "calc_hash_std", "calc_hash_full"]

FieldName = Literal[
    "coupon",
    "day_count",
    "frequency",
    "maturity_date",
    "issue_date",
    "first_coupon_date",
    "calendar",
    "business_day_convention",
]

FieldStatus = Literal["explicit", "derived", "default", "unknown"]

Confidence = Literal["high", "medium", "low"]


class TierHashes(TypedDict, total=False):
    calc_hash_min: str
    calc_hash_std: str
    calc_hash_full: str


class StructuralFlags(TypedDict, total=False):
    is_bullet: bool
    is_sinker: bool
    is_amortizing: bool
    is_callable: bool
    is_putable: bool
    is_floater: bool
    is_step_up: bool
    is_step_down: bool
    has_make_whole: bool
    is_zero_coupon: bool


class SourceReference(TypedDict, total=False):
    id: str
    kind: Literal[
        "prospectus",
        "supplement",
        "etf_holding",
        "exchange_filing",
        "issuer_disclosure",
        "vendor_consensus",
        "other",
    ]
    url: str
    page: int
    asof: str
    note: str


# WhereToFind is a dict[FieldName, list[SourceReference]] but TypedDict can't
# express that cleanly; treat it as a dict at runtime.
WhereToFind = dict[str, list[SourceReference]]


# ---- top-level wire types ----

class PublishedRecord(TypedDict, total=False):
    isin: str
    schema_version: str
    asof: str
    tier_hashes: TierHashes
    structural_flags: StructuralFlags
    canonical_field_status: dict[str, FieldStatus]
    confidence: Confidence
    sources: list[SourceReference]
    where_to_find: WhereToFind


class TierResult(TypedDict, total=False):
    match: bool | None
    reason: str


class ValidationBlock(TypedDict, total=False):
    match: bool
    highest_tier_compared: TierName | None
    tier_results: dict[str, TierResult]
    missing_for_higher_tiers: list[str]
    mismatched_at_tier: TierName | None
    fields_implicated_by_mismatch: list[str]
    where_to_find: WhereToFind
    warnings: list[str]


class ValidateRequest(TypedDict, total=False):
    isin: str
    client_tier_hashes: TierHashes
    client_field_presence: list[str]
    schema_version: str


class ValidateResponse(TypedDict):
    record: PublishedRecord
    validation: ValidationBlock
