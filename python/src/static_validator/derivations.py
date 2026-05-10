"""Canonical derivations for missing optional fields per SCHEMA.md §4.

When a client doesn't have an explicit value for an optional field, they MUST
apply these rules to populate the field before hashing. This makes the hash
deterministic across clients regardless of which fields they hold explicitly.

Calendar arithmetic uses the rule: same day-of-month if it exists in the
target month, else last day of the target month. (e.g. 2026-03-31 - 1 month
= 2026-02-28.)
"""

from __future__ import annotations

import calendar as _stdlib_calendar
from datetime import date
from typing import Any

DEFAULT_CALENDAR = "NULL_CALENDAR"
DEFAULT_BDC = "UNADJUSTED"


def _months_per_period(frequency: int) -> int:
    if frequency == 1:
        return 12
    if frequency == 2:
        return 6
    if frequency == 4:
        return 3
    if frequency == 12:
        return 1
    if frequency == 0:
        # Zero-coupon — no periods. Caller must not invoke derivation
        # for zero-coupon optional dates.
        raise ValueError("frequency=0 (zero-coupon) has no period; cannot derive coupon dates")
    raise ValueError(f"unsupported frequency: {frequency}")


def _add_months(base: date, months: int) -> date:
    """Add ``months`` calendar months to ``base``, clamping to month length."""
    total = base.month - 1 + months
    year = base.year + total // 12
    month = total % 12 + 1
    last_day = _stdlib_calendar.monthrange(year, month)[1]
    day = min(base.day, last_day)
    return date(year, month, day)


def _derive_first_coupon_date(
    maturity: date,
    frequency: int,
    issue: date | None,
) -> date:
    """Derive ``first_coupon_date`` per SCHEMA.md §4.

    `maturity_date - N × frequency_period`, where N is the largest integer
    such that the result is on or after `issue_date` (if known) or on or
    after `today - 100 years` (if not).
    """
    months = _months_per_period(frequency)
    floor = issue if issue is not None else _add_months(date.today(), -100 * 12)

    # Walk backwards from maturity in period steps until just before floor.
    # The "first coupon" sits one period after the floor.
    cursor = maturity
    while True:
        prev = _add_months(cursor, -months)
        if prev < floor:
            return cursor
        cursor = prev


def _derive_issue_date(first_coupon: date, frequency: int) -> date:
    """Derive ``issue_date`` as ``first_coupon_date - 1 × frequency_period``."""
    months = _months_per_period(frequency)
    return _add_months(first_coupon, -months)


def apply_derivations(record: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``record`` with canonical derivations filled in.

    Mandatory fields must already be present and valid. Missing optional
    fields (issue_date, first_coupon_date, calendar, business_day_convention)
    are derived per SCHEMA.md §4. Explicit values are NEVER overwritten.

    For zero-coupon bonds (frequency=0), issue_date and first_coupon_date
    cannot be derived — they must be explicit, or omitted entirely (caller
    will then only be able to hash at the calc_hash_min tier).
    """
    out = dict(record)

    maturity_str = out["maturity_date"]
    maturity = date.fromisoformat(maturity_str) if isinstance(maturity_str, str) else maturity_str
    frequency = int(out["frequency"])

    has_issue = "issue_date" in out
    has_first = "first_coupon_date" in out
    issue: date | None = None
    if has_issue:
        v = out["issue_date"]
        issue = date.fromisoformat(v) if isinstance(v, str) else v

    if frequency == 0:
        # Zero-coupon — no derivation possible. Leave as-is.
        return out

    # Derive first_coupon_date if missing, using issue_date as floor when known.
    if not has_first:
        derived_first = _derive_first_coupon_date(maturity, frequency, issue)
        out["first_coupon_date"] = derived_first.isoformat()

    # Derive issue_date if missing, from first_coupon_date.
    if not has_issue:
        first_str = out["first_coupon_date"]
        first = date.fromisoformat(first_str) if isinstance(first_str, str) else first_str
        derived_issue = _derive_issue_date(first, frequency)
        out["issue_date"] = derived_issue.isoformat()

    if "calendar" not in out:
        out["calendar"] = DEFAULT_CALENDAR
    if "business_day_convention" not in out:
        out["business_day_convention"] = DEFAULT_BDC

    return out
