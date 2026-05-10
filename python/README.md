# static-validator (Python)

Reference Python implementation of the [static-validator](https://github.com/urbancanary/static-validator) canonical bond static schema.

See the [project root README](../README.md) for the trust model and overall architecture, and [SCHEMA.md](../SCHEMA.md) for the canonical schema specification.

## Install

```bash
pip install -e .[dev]
```

## Usage

### Library

```python
from static_validator import compute_all_tiers, validate_bond_static

# Compute tier hashes for a local bond record.
my_bond = {
    "isin": "US698299BL70",
    "coupon": 3.87,
    "maturity_date": "2060-07-23",
    "frequency": 2,
    "day_count": "BOND_BASIS_30_360",
    "issue_date": "2020-09-30",
    "first_coupon_date": "2021-01-23",
}
hashes = compute_all_tiers(my_bond)

# Compare against canonical hashes (e.g. from the public read API).
canonical = {
    "calc_hash_min": "sha256:...",
    "calc_hash_std": "sha256:...",
    "calc_hash_full": "sha256:...",
}
result = validate_bond_static(my_bond, canonical)
print(result.match, result.tier_used, result.mismatched_fields)
```

### Normalization adapter (Layer A)

Take raw vendor-shaped bond static (possibly with ambiguous strings like `"30/360"` and null fields) and produce a wire-format `PublishedRecord` with conservative resolution policy:

```python
from datetime import date
from static_validator import normalize_to_published_record, disambiguate_day_count

# Pure resolver — no IO. Multi-source observations + optional prospectus text.
res = disambiguate_day_count(
    raw="30/360",
    isin="US698299BL70",
    observations={"emb": "BOND_BASIS_30_360", "lqd": "BOND_BASIS_30_360"},
    prospectus_text="computed on the basis of a 360-day year consisting of twelve 30-day months",
)
print(res.canonical, res.confidence)  # BOND_BASIS_30_360 high

# Full pipeline — produces a PublishedRecord conforming to schema/published_record.schema.json.
record = normalize_to_published_record(
    raw_row={
        "coupon": 3.87,
        "maturity_date": "2060-07-23",
        "frequency": 2,
        "day_count": "30/360",          # ambiguous — adapter will resolve via prospectus
        "issue_date": "2020-09-30",
        "first_coupon_date": "2021-01-23",
    },
    isin="US698299BL70",
    asof=date(2026, 5, 10),
    structural_flags={"is_bullet": False, "is_sinker": True},
    sources=[{"id": "EDGAR-424B5-...", "kind": "prospectus"}],
    prospectus_text="...360-day year consisting of twelve 30-day months...",
)
# Resolved → record["tier_hashes"] populated, canonical_field_status.day_count == "explicit".
# Unresolved → record["tier_hashes"] == {}, where_to_find["day_count"] populated.
```

Resolution policy is conservative: ISIN-prefix heuristics never tip the answer, vendor consensus needs 2+ sources, and prospectus phrases must match a definitive pattern. Bonds the adapter cannot resolve are surfaced — never silently guessed.

### CLI

```bash
# Hash a record at all available tiers.
static-validator hash --json my_bond.json

# Hash at a single tier.
static-validator hash --json my_bond.json --tier calc_hash_std

# Emit canonical JSON for a tier (useful for debugging).
static-validator canonical --json my_bond.json --tier calc_hash_full
```

## Tests

```bash
pytest tests/ -v
```

The test suite includes:
- Canonical JSON serialization tests (RFC 8785 + schema constraints)
- Derivation tests for missing optional fields
- Tier hash determinism + sensitivity tests
- Golden fixtures for known bonds (currently: PANAMA 2060)

## License

MIT.
