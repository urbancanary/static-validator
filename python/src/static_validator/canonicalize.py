"""Canonical JSON serialization per SCHEMA.md §5.

Two implementations MUST produce byte-identical output for the same logical
input. Any change here is a schema-breaking change and requires a MAJOR version
bump.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal
from typing import Any

_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Coupon and other decimal fields: 6 dp max, normalized — no trailing zeros
# after the decimal point, no leading +.
_MAX_DECIMAL_PLACES = 6


def _validate_isin_checksum(isin: str) -> bool:
    """Luhn-style ISO 6166 checksum validation."""
    digits: list[int] = []
    for ch in isin[:-1]:
        if ch.isdigit():
            digits.append(int(ch))
        else:
            n = ord(ch) - ord("A") + 10
            digits.append(n // 10)
            digits.append(n % 10)
    total = 0
    parity = (len(digits) - 1) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    check = (10 - (total % 10)) % 10
    return check == int(isin[-1])


def _normalize_number(value: Any) -> int | float:
    """Normalize coupon-style decimals to the canonical form.

    Integers stay integers. Decimals round to 6 dp and emit shortest form.
    Used when comparing logical values (e.g. in tests). For canonical-JSON
    output, see _format_number_text.
    """
    text = _format_number_text(value)
    if "." in text:
        return float(text)
    return int(text)


def _format_number_text(value: Any) -> str:
    """Return the canonical JSON text form of a number.

    Integers: shortest decimal, no leading zeros, no trailing .0.
    Decimals: up to 6 dp, no trailing zeros after the point, no leading +,
    negative zero collapsed to 0.
    """
    if isinstance(value, bool):
        raise ValueError("booleans are not numbers in the canonical schema")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (float, Decimal, str)):
        d = Decimal(str(value)).quantize(Decimal(10) ** -_MAX_DECIMAL_PLACES)
        s = format(d, "f")
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        if s in ("", "-"):
            s = "0"
        if s == "-0":
            s = "0"
        return s
    raise TypeError(f"unsupported numeric type: {type(value).__name__}")


def _normalize_string(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError(f"expected string, got {type(value).__name__}")
    return unicodedata.normalize("NFC", value)


def _normalize_date(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        if not _DATE_RE.match(value):
            raise ValueError(f"date must be ISO 8601 YYYY-MM-DD, got {value!r}")
        # Validate it parses.
        date.fromisoformat(value)
        return value
    raise TypeError(f"unsupported date type: {type(value).__name__}")


def _serialize_value(value: Any) -> str:
    """Recursively serialize a single value into canonical JSON text."""
    if value is None:
        # Null is forbidden per SCHEMA.md §5(7); optional fields must be
        # present (with derived value) or absent.
        raise ValueError("null is forbidden in canonical records")
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, Decimal)):
        return _format_number_text(value)
    if isinstance(value, str):
        return _serialize_string_literal(_normalize_string(value))
    if isinstance(value, dict):
        items = sorted(value.items(), key=lambda kv: kv[0].encode("utf-8"))
        body = ",".join(
            f"{_serialize_string_literal(_normalize_string(k))}:{_serialize_value(v)}"
            for k, v in items
        )
        return "{" + body + "}"
    if isinstance(value, list):
        body = ",".join(_serialize_value(v) for v in value)
        return "[" + body + "]"
    raise TypeError(f"unsupported value type: {type(value).__name__}")


def _serialize_string_literal(s: str) -> str:
    out: list[str] = ['"']
    for ch in s:
        cp = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\b":
            out.append("\\b")
        elif ch == "\f":
            out.append("\\f")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif cp < 0x20:
            out.append(f"\\u{cp:04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def canonicalize_record(record: dict[str, Any]) -> dict[str, Any]:
    """Validate, normalize, and return a record ready for serialization.

    Does NOT apply derivations for missing fields — that is the caller's
    responsibility (see derivations.apply_derivations). This function only
    enforces the per-field type and format rules.
    """
    if "isin" not in record:
        raise ValueError("isin is mandatory")
    isin = record["isin"]
    if not isinstance(isin, str) or not _ISIN_RE.match(isin):
        raise ValueError(f"invalid ISIN format: {isin!r}")
    if not _validate_isin_checksum(isin):
        raise ValueError(f"ISIN checksum failed: {isin!r}")

    out: dict[str, Any] = {}

    # Mandatory fields.
    out["isin"] = isin
    if "coupon" not in record:
        raise ValueError("coupon is mandatory")
    out["coupon"] = _normalize_number(record["coupon"])
    if "maturity_date" not in record:
        raise ValueError("maturity_date is mandatory")
    out["maturity_date"] = _normalize_date(record["maturity_date"])
    if "frequency" not in record:
        raise ValueError("frequency is mandatory")
    if record["frequency"] not in (0, 1, 2, 4, 12):
        raise ValueError(f"frequency must be one of 0,1,2,4,12; got {record['frequency']!r}")
    out["frequency"] = int(record["frequency"])
    if "day_count" not in record:
        raise ValueError("day_count is mandatory")
    out["day_count"] = _normalize_string(record["day_count"])

    # Optional fields — pass through if present, derivations are applied
    # upstream by the caller.
    if "issue_date" in record:
        out["issue_date"] = _normalize_date(record["issue_date"])
    if "first_coupon_date" in record:
        out["first_coupon_date"] = _normalize_date(record["first_coupon_date"])
    if "calendar" in record:
        out["calendar"] = _normalize_string(record["calendar"])
    if "business_day_convention" in record:
        out["business_day_convention"] = _normalize_string(record["business_day_convention"])

    return out


def canonicalize_json(record: dict[str, Any]) -> str:
    """Return the canonical JSON text for a record.

    Caller should apply derivations first if any optional fields are missing
    (see derivations.apply_derivations).
    """
    normalized = canonicalize_record(record)
    return _serialize_value(normalized)
