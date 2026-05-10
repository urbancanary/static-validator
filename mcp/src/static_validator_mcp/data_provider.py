"""Resolves an ISIN to a canonical PublishedRecord.

v0.1 strategy: read from JSON files bundled with the package. When the public
read API ships, this module gains a remote fetch path; the tool layer above
stays unchanged.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Iterable


def _fixtures_dir() -> Path:
    return Path(str(resources.files("static_validator_mcp").joinpath("fixtures")))


@lru_cache(maxsize=1)
def _index() -> dict[str, Path]:
    """ISIN → fixture path. Lazily built on first call."""
    out: dict[str, Path] = {}
    for path in _fixtures_dir().glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        isin = data.get("isin")
        if isinstance(isin, str):
            out[isin] = path
    return out


def known_isins() -> list[str]:
    return sorted(_index().keys())


def fetch_published_record(isin: str) -> dict | None:
    """Return the canonical PublishedRecord for an ISIN, or None if unknown."""
    path = _index().get(isin)
    if path is None:
        return None
    return json.loads(path.read_text())


def all_records() -> Iterable[dict]:
    for path in _index().values():
        yield json.loads(path.read_text())
