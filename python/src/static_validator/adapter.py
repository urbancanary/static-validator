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
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
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


# ---- Calendar synonyms ----
#
# Common vendor / desk shorthands → canonical CALENDAR_ENUM. Keys are matched
# after normalising the input through ``_synonym_key`` (uppercase, separators
# collapsed to a single space). A "US" or "USD" alone is intentionally
# *ambiguous* between US_SETTLEMENT and US_GOVERNMENT and is left unresolved
# with a hint, mirroring the day_count "30/360" pattern.

_CALENDAR_SYNONYMS: dict[str, str] = {
    "NULL": "NULL_CALENDAR",
    "NULL CALENDAR": "NULL_CALENDAR",
    "NONE": "NULL_CALENDAR",
    "NO ADJUSTMENT": "NULL_CALENDAR",
    "WEEKEND": "WEEKENDS_ONLY",
    "WEEKENDS": "WEEKENDS_ONLY",
    "WEEKENDS ONLY": "WEEKENDS_ONLY",
    "US SETTLEMENT": "US_SETTLEMENT",
    "NYC": "US_SETTLEMENT",
    "NEW YORK": "US_SETTLEMENT",
    "NYSE": "US_SETTLEMENT",
    "US GOVERNMENT": "US_GOVERNMENT",
    "USGS": "US_GOVERNMENT",
    "FED": "US_GOVERNMENT",
    "FEDERAL RESERVE": "US_GOVERNMENT",
    "US TREASURY": "US_GOVERNMENT",
    "TREASURY": "US_GOVERNMENT",
    "EUR": "TARGET",
    "EURO": "TARGET",
    "TARGET2": "TARGET",
    "T2": "TARGET",
    "ECB": "TARGET",
    "GBP": "UK_SETTLEMENT",
    "UK": "UK_SETTLEMENT",
    "LONDON": "UK_SETTLEMENT",
    "LDN": "UK_SETTLEMENT",
}

_AMBIGUOUS_CALENDAR_HINTS: dict[str, tuple[str, ...]] = {
    "US": ("US_SETTLEMENT", "US_GOVERNMENT"),
    "USD": ("US_SETTLEMENT", "US_GOVERNMENT"),
}


# ---- BDC synonyms ----

_BDC_SYNONYMS: dict[str, str] = {
    "U": "UNADJUSTED",
    "UNADJ": "UNADJUSTED",
    "NONE": "UNADJUSTED",
    "F": "FOLLOWING",
    "FOL": "FOLLOWING",
    "FLW": "FOLLOWING",
    "MF": "MODIFIED_FOLLOWING",
    "MOD FOL": "MODIFIED_FOLLOWING",
    "MOD FOLLOWING": "MODIFIED_FOLLOWING",
    "MODIFIED FOL": "MODIFIED_FOLLOWING",
    "MODIFIED FOLLOWING": "MODIFIED_FOLLOWING",
    "MODFOLLOWING": "MODIFIED_FOLLOWING",
    "MODIFIEDFOLLOWING": "MODIFIED_FOLLOWING",
    "P": "PRECEDING",
    "PREC": "PRECEDING",
    "MP": "MODIFIED_PRECEDING",
    "MOD PREC": "MODIFIED_PRECEDING",
    "MOD PRECEDING": "MODIFIED_PRECEDING",
    "MODIFIED PREC": "MODIFIED_PRECEDING",
    "MODIFIED PRECEDING": "MODIFIED_PRECEDING",
    "MODIFIEDPRECEDING": "MODIFIED_PRECEDING",
}


# ---- Frequency synonyms ----

_FREQUENCY_SYNONYMS: dict[str, int] = {
    "0": 0, "Z": 0, "ZERO": 0, "ZERO COUPON": 0, "ZEROCOUPON": 0, "NONE": 0,
    "1": 1, "A": 1, "ANN": 1, "ANNUAL": 1, "ANNUALLY": 1,
    "2": 2, "S": 2, "SA": 2, "SEMI": 2, "SEMI ANNUAL": 2,
    "SEMIANNUAL": 2, "SEMIANNUALLY": 2, "SEMI ANNUALLY": 2,
    "4": 4, "Q": 4, "QTR": 4, "QUARTER": 4, "QUARTERLY": 4,
    "12": 12, "M": 12, "MO": 12, "MONTH": 12, "MONTHLY": 12,
}


def _synonym_key(s: str) -> str:
    """Uppercase, strip, collapse runs of whitespace / dashes / underscores /
    slashes / dots into a single space. The keys in the synonym tables
    follow this convention."""
    return re.sub(r"[\s\-_/.]+", " ", s.strip().upper()).strip()


# ---- Loose date parsing ----

_MONTH_NAMES: dict[str, int] = {
    "JAN": 1, "JANUARY": 1,
    "FEB": 2, "FEBRUARY": 2,
    "MAR": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4,
    "MAY": 5,
    "JUN": 6, "JUNE": 6,
    "JUL": 7, "JULY": 7,
    "AUG": 8, "AUGUST": 8,
    "SEP": 9, "SEPT": 9, "SEPTEMBER": 9,
    "OCT": 10, "OCTOBER": 10,
    "NOV": 11, "NOVEMBER": 11,
    "DEC": 12, "DECEMBER": 12,
}

_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_COMPACT_ISO_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
_DAY_MONTHNAME_YEAR_RE = re.compile(
    r"^(\d{1,2})[\s\-/]+([A-Za-z]+)[\s\-/,]+(\d{2,4})$"
)
_MONTHNAME_DAY_YEAR_RE = re.compile(
    r"^([A-Za-z]+)[\s\-/]+(\d{1,2})[\s,\-/]+(\d{2,4})$"
)
_NUMERIC_SLASH_RE = re.compile(r"^(\d{1,4})[\-/](\d{1,2})[\-/](\d{1,4})$")

_EXCEL_EPOCH = date(1899, 12, 30)
_EXCEL_SERIAL_MIN = 30000  # ~1982-03-01
_EXCEL_SERIAL_MAX = 75000  # ~2105-04-12


def _resolve_two_digit_year(
    yy: int,
    reference_date: date,
    *,
    assume_future: bool = True,
) -> int:
    """Pivot a 2-digit year against ``reference_date``.

    Forward (``assume_future=True``, the default — for maturity dates):
        ``yy >= ref.year % 100`` → current century, else next century.
        With ref=2026: ``26..99`` → ``2026..2099``; ``00..25`` → ``2100..2125``.
    Backward (``assume_future=False`` — for issue / first-coupon dates):
        ``yy <= ref.year % 100`` → current century, else previous century.
        With ref=2026: ``00..26`` → ``2000..2026``; ``27..99`` → ``1927..1999``.
    """
    if not (0 <= yy <= 99):
        raise ValueError(f"two-digit year out of range: {yy!r}")
    pivot = reference_date.year % 100
    century_base = reference_date.year - pivot
    if assume_future:
        return century_base + yy if yy >= pivot else century_base + 100 + yy
    return century_base + yy if yy <= pivot else century_base - 100 + yy


def parse_loose_date(
    value: object,
    *,
    reference_date: date | None = None,
    assume_future_year: bool = True,
) -> str:
    """Parse a possibly non-canonical date input to ISO 8601 ``YYYY-MM-DD``.

    Accepts:
      - ``date`` / ``datetime``-shaped objects
      - ISO 8601 ``YYYY-MM-DD``
      - Compact ISO ``YYYYMMDD``
      - Textual month: ``5-May-2026``, ``5 May 2026``, ``May 5, 2026``
      - Textual month with 2-digit year: ``5-May-26``. Pivoted against
        ``reference_date`` (defaults to ``date.today()``); forward-leaning
        when ``assume_future_year=True`` (default — appropriate for
        maturity dates), backward-leaning otherwise (for issue and
        first-coupon dates).
      - Year-first all-numeric: ``YYYY/MM/DD``
      - Excel 1900-based serial dates as ``int``/``float`` in
        ``[_EXCEL_SERIAL_MIN, _EXCEL_SERIAL_MAX]``

    Refuses (raises ``ValueError``):
      - All-numeric ``DD/MM/YYYY`` or ``MM/DD/YYYY`` — genuinely ambiguous
        without batch context (resolved by ``infer_batch_format`` in a
        future revision)
      - Anything else
    """
    ref = reference_date or date.today()

    if isinstance(value, bool):
        raise ValueError(f"booleans are not dates: {value!r}")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (int, float)):
        return _excel_serial_to_iso(value)
    if not isinstance(value, str):
        raise TypeError(f"unsupported date type: {type(value).__name__}")

    s = value.strip()
    if not s:
        raise ValueError("empty date string")

    m = _ISO_DATE_RE.match(s)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        return date(y, mo, d).isoformat()

    m = _COMPACT_ISO_RE.match(s)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        return date(y, mo, d).isoformat()

    m = _DAY_MONTHNAME_YEAR_RE.match(s)
    if m:
        d_s, mon_s, y_s = m.group(1), m.group(2).upper(), m.group(3)
        if mon_s not in _MONTH_NAMES:
            raise ValueError(f"unrecognised month name in {value!r}")
        year = _parse_year_field(y_s, value, ref, assume_future_year)
        return date(year, _MONTH_NAMES[mon_s], int(d_s)).isoformat()

    m = _MONTHNAME_DAY_YEAR_RE.match(s)
    if m:
        mon_s, d_s, y_s = m.group(1).upper(), m.group(2), m.group(3)
        if mon_s not in _MONTH_NAMES:
            raise ValueError(f"unrecognised month name in {value!r}")
        year = _parse_year_field(y_s, value, ref, assume_future_year)
        return date(year, _MONTH_NAMES[mon_s], int(d_s)).isoformat()

    m = _NUMERIC_SLASH_RE.match(s)
    if m:
        a_s, b_s, c_s = m.group(1), m.group(2), m.group(3)
        if len(a_s) == 4 and len(c_s) <= 2:
            return date(int(a_s), int(b_s), int(c_s)).isoformat()
        raise ValueError(
            f"date {value!r} is ambiguous: cannot tell DD/MM/YYYY from "
            "MM/DD/YYYY without batch context. Provide ISO 8601 'YYYY-MM-DD' "
            "or a textual month (e.g. '5-May-2026')."
        )

    raise ValueError(f"unrecognised date format: {value!r}")


def _parse_year_field(y_s: str, original: str, ref: date, assume_future: bool) -> int:
    if len(y_s) == 4:
        return int(y_s)
    if len(y_s) == 2:
        return _resolve_two_digit_year(int(y_s), ref, assume_future=assume_future)
    raise ValueError(
        f"date {original!r} has a {len(y_s)}-digit year; expected 2 or 4 digits"
    )


def _excel_serial_to_iso(serial: float) -> str:
    if serial != int(serial):
        n = int(serial)
    else:
        n = int(serial)
    if n < _EXCEL_SERIAL_MIN or n > _EXCEL_SERIAL_MAX:
        raise ValueError(
            f"numeric date {serial!r} is outside the accepted Excel-serial "
            f"window [{_EXCEL_SERIAL_MIN}, {_EXCEL_SERIAL_MAX}]; refusing as "
            "likely misencoded. Provide an ISO 8601 string instead."
        )
    return (_EXCEL_EPOCH + timedelta(days=n)).isoformat()


# ---- Loose coupon parsing ----

def normalize_coupon_value(
    value: object,
    *,
    allow_below_half_pct: bool = False,
) -> int | float:
    """Coerce a coupon input to its canonical numeric form.

    Conservative: refuses values strictly between 0 and 0.5 unless
    ``allow_below_half_pct=True``. A value like ``0.045`` is overwhelmingly
    likely to be a fraction (4.5%) miscoded as a percentage; silently
    accepting it would corrupt the hash. Genuine sub-0.5% coupons (rare
    JGBs, negative-rate-era issuance) require the explicit opt-in.

    Trailing ``%`` is tolerated. Returns ``int`` for whole percentages
    (so the canonical hash sees ``5`` not ``5.0``), ``float`` otherwise.
    """
    if isinstance(value, bool):
        raise ValueError(f"booleans are not coupons: {value!r}")
    if isinstance(value, str):
        s = value.strip().rstrip("%").strip()
        if not s:
            raise ValueError("empty coupon string")
        try:
            num = Decimal(s)
        except InvalidOperation as exc:
            raise ValueError(f"could not parse coupon: {value!r}") from exc
    elif isinstance(value, (int, float, Decimal)):
        num = Decimal(str(value))
    else:
        raise TypeError(f"unsupported coupon type: {type(value).__name__}")

    if num < 0:
        raise ValueError(f"negative coupon: {value!r}")
    if num > Decimal("100"):
        raise ValueError(f"coupon {value!r} > 100%; likely misencoded")
    if num != 0 and num < Decimal("0.5") and not allow_below_half_pct:
        raise ValueError(
            f"coupon {value!r} looks like a fraction (e.g. 0.045 meaning "
            "4.5%), not a percentage. The schema requires percentage form: "
            "use 4.5 not 0.045. If this is a genuine sub-0.5% coupon, pass "
            "allow_below_half_pct=True."
        )

    if num == num.to_integral_value():
        return int(num)
    return float(num)


# ---- Loose frequency parsing ----

def normalize_frequency(value: object) -> int:
    """Resolve a frequency input to one of {0, 1, 2, 4, 12}.

    Accepts integers, numeric strings, and common shorthands
    (``S``/``A``/``Q``/``M``/``Z``, ``Semi-Annual``, ``Quarterly``, etc.).
    """
    if isinstance(value, bool):
        raise ValueError(f"booleans are not frequencies: {value!r}")
    if isinstance(value, int):
        if value not in (0, 1, 2, 4, 12):
            raise ValueError(
                f"frequency {value!r} is not one of 0, 1, 2, 4, 12"
            )
        return value
    if isinstance(value, str):
        key = _synonym_key(value)
        if not key:
            raise ValueError("empty frequency string")
        if key in _FREQUENCY_SYNONYMS:
            return _FREQUENCY_SYNONYMS[key]
        raise ValueError(
            f"frequency {value!r} is not a recognised value or synonym; "
            "expected one of 0, 1, 2, 4, 12 or S/A/Q/M/Z."
        )
    raise TypeError(f"unsupported frequency type: {type(value).__name__}")


# ---- Disambiguators ----

def _is_canonical(value: str | None, enum_set: frozenset[str]) -> bool:
    return isinstance(value, str) and value in enum_set


def _through_synonyms(
    value: str | None,
    enum_set: frozenset[str],
    synonyms: dict[str, str],
    ambiguous: dict[str, tuple[str, ...]] | None,
) -> tuple[str | None, tuple[str, ...] | None]:
    """Return ``(canonical, ambiguous_candidates)``.

    - Canonical raw → ``(value, None)``
    - Synonym match → ``(canonical, None)``
    - Ambiguous shorthand → ``(None, candidates)``
    - None / unrecognised → ``(None, None)``
    """
    if value is None or not isinstance(value, str):
        return None, None
    if value in enum_set:
        return value, None
    key = _synonym_key(value)
    # Mixed-case spellings of a canonical form (e.g. "Preceding",
    # "us_settlement") are accepted via this path before consulting the
    # synonym table.
    canonical_match = key.replace(" ", "_")
    if canonical_match in enum_set:
        return canonical_match, None
    if key in synonyms:
        return synonyms[key], None
    if ambiguous and key in ambiguous:
        return None, ambiguous[key]
    return None, None


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
    synonyms: dict[str, str],
    ambiguous_hints: dict[str, tuple[str, ...]] | None,
    observations: dict[str, str] | None,
) -> FieldResolution:
    """Used for calendar and BDC. The raw value is accepted if it is already
    canonical, mapped via the synonym table, or absent (in which case the
    canonical default applies). Ambiguous shorthands (e.g. bare ``"US"``)
    are left unresolved with a hint."""
    observations = dict(observations or {})
    reasoning: list[str] = []

    canonical, candidates = _through_synonyms(raw, enum_set, synonyms, ambiguous_hints)

    if canonical is not None:
        if raw != canonical:
            reasoning.append(f"primary value {raw!r} mapped via synonym to {canonical!r}")
        canonical_obs: list[tuple[str, str]] = []
        for src, val in observations.items():
            obs_can, _ = _through_synonyms(val, enum_set, synonyms, ambiguous_hints)
            if obs_can is not None:
                canonical_obs.append((src, obs_can))
        agree = sum(1 for _, v in canonical_obs if v == canonical)
        if agree >= 2:
            reasoning.append(f"confirmed by {agree} observation(s)")
            sources_used = ["primary"] + [s for s, v in canonical_obs if v == canonical]
            return FieldResolution(canonical, "high", "explicit", reasoning, sources_used)
        if raw == canonical:
            reasoning.append(f"primary value {raw!r} accepted (single source)")
        return FieldResolution(canonical, "low", "explicit", reasoning, ["primary"])

    if raw is None:
        reasoning.append(
            f"primary record has no value; canonical default {default_value!r} applied"
        )
        return FieldResolution(default_value, "high", "default", reasoning, [])

    if candidates is not None:
        reasoning.append(
            f"primary value {raw!r} is ambiguous; possible canonical forms: "
            f"{', '.join(candidates)}"
        )
        return FieldResolution(None, "unresolved", "unknown", reasoning, [])

    reasoning.append(
        f"primary value {raw!r} is not a recognised canonical enum or known synonym; "
        "left unresolved (consider sourcing from prospectus)"
    )
    return FieldResolution(None, "unresolved", "unknown", reasoning, [])


def disambiguate_calendar(
    raw: str | None,
    isin: str,
    observations: dict[str, str] | None = None,
) -> FieldResolution:
    return _disambiguate_simple_enum(
        raw, CALENDAR_ENUM, DEFAULT_CALENDAR,
        _CALENDAR_SYNONYMS, _AMBIGUOUS_CALENDAR_HINTS, observations,
    )


def disambiguate_bdc(
    raw: str | None,
    isin: str,
    observations: dict[str, str] | None = None,
) -> FieldResolution:
    return _disambiguate_simple_enum(
        raw, BDC_ENUM, DEFAULT_BDC,
        _BDC_SYNONYMS, None, observations,
    )


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
    allow_below_half_pct_coupon: bool = False,
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

    # Mandatory fields, normalised through the loose-input helpers so that
    # ambiguous formats (Excel serials, percent-vs-fraction coupons, "Semi"
    # frequency, etc.) are caught here instead of corrupting the hash.
    for field_name in ("coupon", "maturity_date", "frequency"):
        if field_name not in raw_row or raw_row[field_name] is None:
            raise ValueError(f"raw_row is missing mandatory field {field_name!r}")
    canonical_record["coupon"] = normalize_coupon_value(
        raw_row["coupon"], allow_below_half_pct=allow_below_half_pct_coupon,
    )
    field_status["coupon"] = "explicit"
    canonical_record["maturity_date"] = parse_loose_date(
        raw_row["maturity_date"], reference_date=asof,
    )
    field_status["maturity_date"] = "explicit"
    canonical_record["frequency"] = normalize_frequency(raw_row["frequency"])
    field_status["frequency"] = "explicit"

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

    # Optional dates: parse loosely if present; otherwise mark as derived
    # (apply_derivations will fill them at hash time).
    for field_name in ("issue_date", "first_coupon_date"):
        v = raw_row.get(field_name)
        if v is not None:
            # These fields are backward-leaning: a 2-digit year is almost
            # always recent past, not the next century.
            canonical_record[field_name] = parse_loose_date(
                v, reference_date=asof, assume_future_year=False,
            )
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
    "normalize_coupon_value",
    "normalize_frequency",
    "normalize_to_published_record",
    "parse_loose_date",
]
