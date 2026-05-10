"""JSON Schema conformance tests for the wire contract.

Validates the golden fixtures and SDK-produced records against the canonical
JSON Schema files in ../../schema/. Both the SDK and any future server
implementation must pass these.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

REPO_ROOT = Path(__file__).parents[2]
SCHEMA_DIR = REPO_ROOT / "schema"
GOLDEN_DIR = Path(__file__).parent / "golden"


def _registry() -> Registry:
    """Build a referencing.Registry over every schema file in /schema/.

    The schemas use $id URIs but $ref by relative filename. The registry
    resolves both.
    """
    reg = Registry()
    for path in SCHEMA_DIR.glob("*.schema.json"):
        contents = json.loads(path.read_text())
        resource = Resource.from_contents(contents)
        # Register under both the absolute $id and the bare filename.
        reg = reg.with_resource(uri=contents["$id"], resource=resource)
        reg = reg.with_resource(uri=path.name, resource=resource)
    return reg


@pytest.fixture(scope="module")
def registry():
    return _registry()


def _validate(instance: dict, schema_filename: str, registry) -> None:
    schema = json.loads((SCHEMA_DIR / schema_filename).read_text())
    Draft202012Validator(schema, registry=registry).validate(instance)


class TestPublishedRecordSchema:
    def test_panama_golden_conforms(self, registry):
        record = json.loads((GOLDEN_DIR / "panama_2060.expected.json").read_text())
        _validate(record, "published_record.schema.json", registry)

    def test_missing_required_rejected(self, registry):
        record = json.loads((GOLDEN_DIR / "panama_2060.expected.json").read_text())
        del record["isin"]
        with pytest.raises(jsonschema.ValidationError):
            _validate(record, "published_record.schema.json", registry)

    def test_bad_isin_pattern_rejected(self, registry):
        record = json.loads((GOLDEN_DIR / "panama_2060.expected.json").read_text())
        record["isin"] = "BAD"
        with pytest.raises(jsonschema.ValidationError):
            _validate(record, "published_record.schema.json", registry)

    def test_bad_tier_hash_pattern_rejected(self, registry):
        record = json.loads((GOLDEN_DIR / "panama_2060.expected.json").read_text())
        record["tier_hashes"]["calc_hash_min"] = "md5:abc123"
        with pytest.raises(jsonschema.ValidationError):
            _validate(record, "published_record.schema.json", registry)


class TestValidateRequestSchema:
    def test_minimal_valid(self, registry):
        req = {
            "isin": "US698299BL70",
            "client_tier_hashes": {
                "calc_hash_min": "sha256:" + "0" * 64,
            },
            "client_field_presence": ["coupon", "day_count", "frequency", "maturity_date"],
            "schema_version": "0.1",
        }
        _validate(req, "validate_request.schema.json", registry)

    def test_field_value_in_request_rejected(self, registry):
        """Critical privacy property: the schema must REFUSE any request that
        carries a field value (e.g. client_static, payload, body) — only the
        ISIN, hashes, and field-presence bitmap are permitted.
        """
        req = {
            "isin": "US698299BL70",
            "client_tier_hashes": {"calc_hash_min": "sha256:" + "0" * 64},
            "client_field_presence": ["coupon"],
            "schema_version": "0.1",
            "client_static": {"coupon": 3.87},  # FORBIDDEN
        }
        with pytest.raises(jsonschema.ValidationError):
            _validate(req, "validate_request.schema.json", registry)

    def test_unknown_field_in_presence_rejected(self, registry):
        req = {
            "isin": "US698299BL70",
            "client_tier_hashes": {"calc_hash_min": "sha256:" + "0" * 64},
            "client_field_presence": ["coupon", "ratings"],  # 'ratings' not in v0.1
            "schema_version": "0.1",
        }
        with pytest.raises(jsonschema.ValidationError):
            _validate(req, "validate_request.schema.json", registry)
