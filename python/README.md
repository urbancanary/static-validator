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
