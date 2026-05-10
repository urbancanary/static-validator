"""CLI: hash bond static and emit canonical JSON.

Usage:
    python -m static_validator hash --json bond.json
    python -m static_validator hash --json bond.json --tier calc_hash_std
    python -m static_validator canonical --json bond.json --tier calc_hash_full
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .canonicalize import canonicalize_json
from .derivations import apply_derivations
from .hashes import ALL_TIERS, _TIER_FIELDS, compute_all_tiers, compute_tier_hash


def _load(path: str) -> dict:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="static_validator")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_hash = sub.add_parser("hash", help="compute tier hashes for a bond record")
    p_hash.add_argument("--json", required=True, help="path to JSON record, or - for stdin")
    p_hash.add_argument("--tier", choices=ALL_TIERS, help="single tier (default: all available)")

    p_canon = sub.add_parser("canonical", help="emit canonical JSON for a bond record at a tier")
    p_canon.add_argument("--json", required=True)
    p_canon.add_argument("--tier", choices=ALL_TIERS, default="calc_hash_std")

    args = parser.parse_args(argv)
    record = _load(args.json)

    if args.cmd == "hash":
        if args.tier:
            print(json.dumps({args.tier: compute_tier_hash(record, args.tier)}, indent=2))
        else:
            print(json.dumps(compute_all_tiers(record), indent=2))
        return 0

    if args.cmd == "canonical":
        derived = apply_derivations(record)
        fields = _TIER_FIELDS[args.tier]
        projected = {f: derived[f] for f in fields if f in derived}
        sys.stdout.write(canonicalize_json(projected))
        sys.stdout.write("\n")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
