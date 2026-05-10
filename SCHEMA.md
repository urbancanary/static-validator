# Canonical Schema v0.1

This document defines how a bond's static data is normalized and hashed for the static-validator project. It is the load-bearing contract: every SDK, every Worker, every customer reimplementation must produce byte-identical canonical JSON for the same input, and therefore byte-identical hashes. Get this wrong and the entire trust property collapses.

> **Status:** v0.1 draft. Under active iteration. Field set, derivation rules, and tier definitions may change before v1.0. Versioning is in §7.

---

## 1. Scope

The schema covers the fields needed to reproduce a vanilla bullet bond's accrual and yield calculation in a deterministic way. It does not attempt to cover callables, sinkers, floaters, step-ups, or other structurally non-standard bonds in v0.1; those are out of scope until a future version (`structured_hash`) addresses them explicitly.

A bond is identified by its ISIN. The hash is per-ISIN.

## 2. Field set

| Field | Type | Mandatory? | Notes |
|---|---|---|---|
| `isin` | string | yes | 12-character ISO 6166 ISIN. Validated against checksum. |
| `coupon` | decimal | yes | Annual coupon rate as a percentage. e.g. `4.5` not `0.045`. 6 dp max. |
| `maturity_date` | date | yes | Final principal repayment date. ISO 8601 `YYYY-MM-DD`. |
| `frequency` | integer | yes | Coupon payments per year. One of `{0, 1, 2, 4, 12}`. `0` = zero-coupon. |
| `day_count` | enum | yes | One of the values in §3. |
| `issue_date` | date | optional | First settlement date. ISO 8601. Derivation rule in §4. |
| `first_coupon_date` | date | optional | First coupon payment date. ISO 8601. Derivation rule in §4. |
| `calendar` | enum | optional | One of the values in §3. Default per §4. |
| `business_day_convention` | enum | optional | One of the values in §3. Default per §4. |

Fields not listed here are NOT part of v0.1 canonical hashes. Adding a field requires a schema version bump (§7).

## 3. Enum values

These enum names are normative. SDKs MUST emit exactly these strings; no synonyms.

### `day_count`

ISDA 2006 day-count names. Never use ambiguous strings like `"30/360"` without a qualifier.

| Canonical name | Description |
|---|---|
| `BOND_BASIS_30_360` | 30/360 Bond Basis (US municipal/corporate convention) |
| `ISMA_30_360` | 30E/360 ISMA |
| `ISDA_30E_360` | 30E/360 ISDA (a.k.a. Eurobond Basis) |
| `ACT_ACT_ICMA` | Actual/Actual ICMA |
| `ACT_ACT_ISDA` | Actual/Actual ISDA |
| `ACT_360` | Actual/360 |
| `ACT_365_FIXED` | Actual/365 Fixed |
| `ACT_365_25` | Actual/365.25 |

### `calendar`

| Canonical name | Description |
|---|---|
| `NULL_CALENDAR` | Every day is a business day. Default for accrual-only calculations. |
| `WEEKENDS_ONLY` | Saturdays and Sundays are non-business days. |
| `US_GOVERNMENT` | US government bond market calendar. |
| `US_SETTLEMENT` | US settlement calendar. |
| `TARGET` | TARGET (EUR) calendar. |
| `UK_SETTLEMENT` | UK settlement calendar. |

(Additional calendars to be added on demand. PR via issue first.)

### `business_day_convention`

| Canonical name | Description |
|---|---|
| `UNADJUSTED` | No adjustment for non-business days. |
| `FOLLOWING` | Next business day. |
| `MODIFIED_FOLLOWING` | Next business day, unless that crosses a month boundary, then previous. |
| `PRECEDING` | Previous business day. |
| `MODIFIED_PRECEDING` | Previous business day, unless that crosses a month boundary, then next. |

## 4. Canonical derivations for missing optional fields

If a client does not have an explicit value for an optional field, they MUST apply the canonical derivation rule below to populate the field before hashing. This makes the hash deterministic across clients regardless of which fields they happen to hold explicitly.

| Field | Derivation when not given |
|---|---|
| `issue_date` | `first_coupon_date - 1 × frequency_period`. If `first_coupon_date` is also not given, derive `first_coupon_date` first per the rule below, then derive `issue_date`. |
| `first_coupon_date` | `maturity_date - N × frequency_period`, where N is the largest integer such that the result is on or after `issue_date` (if known) or on or after `today - 100 years` (if not). Periods are computed as exact calendar months: `frequency=2` → 6 months, `frequency=4` → 3 months, `frequency=1` → 12 months, `frequency=12` → 1 month. |
| `calendar` | `NULL_CALENDAR`. Note: this default is only safe for accrual and yield calculations; it is NOT safe for OAS or spread calculations against a real curve. |
| `business_day_convention` | `UNADJUSTED`. |

Calendar arithmetic for derivations: add/subtract whole months using the rule "same day-of-month if it exists in target month, else last day of target month" (e.g. `2026-03-31 - 1 month = 2026-02-28`).

## 5. Canonical JSON normalization

Canonical JSON follows [RFC 8785 (JCS)](https://datatracker.ietf.org/doc/html/rfc8785) with the additional constraints below. Two implementations MUST produce byte-identical output for the same logical input.

1. **Object keys** sorted in lexicographic UTF-8 byte order.
2. **No whitespace** outside of strings. No leading/trailing whitespace.
3. **String encoding**: UTF-8, NFC-normalized. JSON escapes only for `\"`, `\\`, `\b`, `\f`, `\n`, `\r`, `\t`, and `\u00XX` for control characters below `0x20`. No unnecessary `\uXXXX` escapes.
4. **Numbers**:
   - Integers: shortest decimal representation, no leading zeros, no trailing `.0`. Negative zero is forbidden; emit `0`.
   - Decimals (coupon, etc.): up to 6 decimal places, normalized — no trailing zeros after the decimal point, no leading `+`. Examples: `4.5`, `4.875`, `0.125`. Forbidden: `4.50`, `+4.5`, `4.500000`.
5. **Dates**: emitted as JSON strings in ISO 8601 `YYYY-MM-DD` form. No timezones, no time component.
6. **Booleans**: `true` / `false`. No quoted strings.
7. **Null**: forbidden in the canonical record. Optional fields MUST be either present (with derived value per §4) or absent.

Reference canonical JSON for a hypothetical bond:

```json
{"business_day_convention":"UNADJUSTED","calendar":"NULL_CALENDAR","coupon":4.5,"day_count":"BOND_BASIS_30_360","first_coupon_date":"2026-08-15","frequency":2,"isin":"US123456AB12","issue_date":"2026-02-15","maturity_date":"2034-08-15"}
```

## 6. Tier hash construction

Hashes are SHA-256 over the canonical JSON of the relevant subset of fields. Three tiers are published per ISIN:

### `calc_hash_min`

Fields: `isin`, `coupon`, `maturity_date`, `frequency`, `day_count`.

For clients whose static is too sparse to compute the higher tiers reliably. Sufficient to detect the most common drift cases (wrong coupon, wrong day count).

### `calc_hash_std`

Fields: `isin`, `coupon`, `maturity_date`, `frequency`, `day_count`, `issue_date`, `first_coupon_date`.

Standard tier. Sufficient to fully reproduce a vanilla bullet bond's accrual schedule.

### `calc_hash_full`

Fields: all of `calc_hash_std` plus `calendar`, `business_day_convention`.

For audit-grade matching where calendar / BDC matter (e.g. settlement-date computations, OAS).

### Construction

```text
canonical_json = JCS_normalize({fields_for_tier})
hash_bytes     = SHA-256(canonical_json.encode("utf-8"))
hash_hex       = lowercase_hex(hash_bytes)
tier_hash      = "sha256:" + hash_hex
```

Example tier hash format: `sha256:9da8fc9cf4ed47053f71a1aa7ead3dc3...` (64 hex chars after the prefix).

The leading `sha256:` prefix is mandatory. It future-proofs the format for algorithm migration (e.g. SHA-3) without breaking parsers.

## 7. Versioning

The schema is versioned `MAJOR.MINOR`.

- **MINOR** bumps for additive, backward-compatible changes (new optional field, new enum value). Existing hashes remain valid.
- **MAJOR** bumps for any change that alters the canonical JSON for the same logical input (renamed field, changed derivation rule, new mandatory field, changed JCS rule). Hashes computed under the old version are no longer authoritative; clients MUST recompute.

The schema version SHOULD be transmitted out-of-band (in the API response envelope, in SDK constants) and MUST be checkable by clients. SDK implementations MUST refuse to mix versions in a single hash comparison.

Current version: **0.1**.

## 8. Out of scope for v0.1

The following are explicitly NOT covered by v0.1 hashes. Future schemas (`structured_hash`, `display_hash`, `rating_hash`) will address them in dedicated versions.

- Callables, putables, sinkers, amortizers, floaters, step-ups
- Display fields (ticker, description, issuer name, country)
- Ratings (Moody's, S&P, Fitch, composite)
- Cashflow schedules (derived from the calc fields; covered by a future `cashflow_hash`)
- Pricing or analytics (yield, duration, OAS, spread — these are computations, not static)

## 9. Open questions for v0.2

- Should `coupon = 0` (zero-coupon) require `frequency = 0` mandatorily, or accept `frequency = 2` with a coupon of zero? Affects schedule derivation.
- Should we publish a `calc_hash_min_no_dc` tier for clients who have everything except day_count (a depressingly common case)? Trade-off: more tiers, weaker collision resistance per tier.
- How do we represent step-up coupons in a future `calc_hash` extension without forcing the `coupon` field to become a list?
- Calendar default (`NULL_CALENDAR`) is unsafe for OAS — should `calc_hash_full` reject `NULL_CALENDAR` as a derived default and force explicit specification?

These will be resolved alongside the v0.2 reference SDK, where implementation forces decisions.
