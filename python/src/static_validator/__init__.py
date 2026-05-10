"""static-validator: canonical bond static hashing and validation."""

from .adapter import (
    FieldResolution,
    classify_day_count_phrase,
    disambiguate_bdc,
    disambiguate_calendar,
    disambiguate_day_count,
    normalize_coupon_value,
    normalize_frequency,
    normalize_to_published_record,
    parse_loose_date,
)
from .gemini_extractor import (
    AmortizationExtraction,
    CallExtraction,
    FieldExtraction,
    ProspectusExtraction,
    VerificationResult,
    quote_in_pdf_text,
    verify_extraction,
)
from .canonicalize import (
    BDC_ENUM,
    CALENDAR_ENUM,
    DAY_COUNT_ENUM,
    canonicalize_json,
    canonicalize_record,
)
from .derivations import apply_derivations
from .hashes import TierName, compute_tier_hash, compute_all_tiers
from .validate import ValidationResult, validate_bond_static

SCHEMA_VERSION = "0.1"

__all__ = [
    "SCHEMA_VERSION",
    "BDC_ENUM",
    "CALENDAR_ENUM",
    "DAY_COUNT_ENUM",
    "canonicalize_json",
    "canonicalize_record",
    "apply_derivations",
    "TierName",
    "compute_tier_hash",
    "compute_all_tiers",
    "ValidationResult",
    "validate_bond_static",
    "AmortizationExtraction",
    "CallExtraction",
    "FieldExtraction",
    "FieldResolution",
    "ProspectusExtraction",
    "VerificationResult",
    "classify_day_count_phrase",
    "disambiguate_bdc",
    "disambiguate_calendar",
    "disambiguate_day_count",
    "normalize_coupon_value",
    "normalize_frequency",
    "normalize_to_published_record",
    "parse_loose_date",
    "quote_in_pdf_text",
    "verify_extraction",
]
