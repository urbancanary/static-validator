# Wire Format

The JSON Schema files in this directory are the single source of truth for the static-validator wire contract. Both the Python SDK and any future TypeScript SDK generate types from these files. Both the Cloudflare Worker (server) and any client (Claude Desktop MCP, Athena UI, customer's own pipeline) validate against them.

If you change a schema here, you change the contract for every consumer. Treat changes the same as `SCHEMA.md` changes — additive at MINOR, breaking at MAJOR.

## Files

| File | Purpose |
|---|---|
| `tier_hashes.schema.json` | Reusable: the three SHA-256 tier hashes per ISIN |
| `structural_flags.schema.json` | Reusable: the structural metadata flags (sinker, callable, etc.) |
| `source_reference.schema.json` | Reusable: a single citation pointing at a public source |
| `where_to_find.schema.json` | Reusable: per-field hints for where to look up missing values |
| `published_record.schema.json` | `GET /hash/{isin}` response body |
| `validate_request.schema.json` | `POST /validate` request body |
| `validate_response.schema.json` | `POST /validate` response body |

## Privacy contract

The request schemas accept only:

1. The public ISIN
2. The client's locally-computed tier hashes (one-way SHA-256)
3. A bitmap of which fields the client has values for — never the values themselves

There is intentionally no field anywhere in any request schema that accepts a coupon, day count, maturity, or any other static value. The wire contract is the enforcement of the "we have no API that accepts your data" property documented in the project README and codebase-mcp memory 298.

## Versioning

Each response includes `schema_version`. Clients MUST refuse to mix versions in a single comparison. Server publishes the schema version it computed under.
