"""MCP server entrypoint.

Exposes three tools to MCP clients:
- list_known_isins: discover which ISINs the validator has canonical
  records for in this installation
- fetch_canonical_record: return the published canonical record for an ISIN
- validate_bond_static: hash the user's local bond static and compare against
  the canonical record

The plain Python helpers are defined first; the MCP tool decorators are thin
wrappers around them. This lets tests exercise the helpers directly without
depending on the MCP transport layer.

All hashing happens locally inside this process. No network call is made
in the bundled-fixtures variant.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from mcp.server.fastmcp import FastMCP

from static_validator import SCHEMA_VERSION, validate_bond_static as sdk_validate

from .data_provider import fetch_published_record, known_isins


# ---- plain helpers (used by both the MCP wrappers and the tests) ----

def list_known_isins_impl() -> dict[str, Any]:
    isins = known_isins()
    return {
        "schema_version": SCHEMA_VERSION,
        "count": len(isins),
        "isins": isins,
    }


def fetch_canonical_record_impl(isin: str) -> dict[str, Any]:
    record = fetch_published_record(isin)
    if record is None:
        return {
            "error": f"no canonical record for ISIN {isin!r} in this installation",
            "known_isins": known_isins(),
        }
    return record


def validate_bond_static_impl(isin: str, bond: dict[str, Any]) -> dict[str, Any]:
    canonical = fetch_published_record(isin)
    if canonical is None:
        return {
            "error": f"no canonical record for ISIN {isin!r} in this installation",
            "known_isins": known_isins(),
        }
    record = dict(bond)
    record.setdefault("isin", isin)
    try:
        result = sdk_validate(record, canonical)
    except (ValueError, TypeError) as exc:
        return {
            "error": f"could not hash supplied bond: {exc}",
            "hint": "check the field values are present and correctly formatted; see schema/published_record.schema.json",
        }
    return asdict(result)


# ---- MCP server + tool registration ----

mcp = FastMCP("static-validator")


@mcp.tool()
def list_known_isins() -> dict[str, Any]:
    """List the ISINs this installation has canonical records for.

    Useful as a discovery call when starting a session — confirms the
    validator is reachable and which bonds it can validate today.
    """
    return list_known_isins_impl()


@mcp.tool()
def fetch_canonical_record(isin: str) -> dict[str, Any]:
    """Return the canonical PublishedRecord for a bond by ISIN.

    The record contains:
    - tier_hashes: SHA-256 hashes of the canonical static at three field-set tiers
    - structural_flags: sinker / callable / floater / step-up flags
    - canonical_field_status: which fields the canonical record has explicitly
    - confidence: high / medium / low based on multi-source consensus
    - sources: citations (typically prospectus URLs)
    - where_to_find: hints for fields the canonical record does not carry
    """
    return fetch_canonical_record_impl(isin)


@mcp.tool()
def validate_bond_static(isin: str, bond: dict[str, Any]) -> dict[str, Any]:
    """Validate a local bond record against the canonical PublishedRecord.

    Args:
        isin: the bond's 12-character ISIN
        bond: the user's local static — must include coupon, maturity_date,
              frequency, day_count; may include issue_date, first_coupon_date,
              calendar, business_day_convention.

    The bond data is hashed inside this process. The hashes are compared
    against the canonical record's hashes. Result reports tier match,
    mismatched fields, structural warnings (e.g. sinker schedule), and
    where to source any missing or mismatched fields.
    """
    return validate_bond_static_impl(isin, bond)


def main() -> None:
    """Entrypoint installed as the `static-validator-mcp` console script."""
    mcp.run()


if __name__ == "__main__":
    main()
