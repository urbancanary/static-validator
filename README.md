# static-validator

A free, open utility for validating bond static data against a canonical reference, without disclosing your data to any third party.

**Status:** v0.1 — schema spec only. Reference SDK and read API land in subsequent releases. The schema and trust model are stable enough to design against; expect minor revisions before v1.0.

---

## What this is

A specification, reference SDK, and free read API that lets you check whether your bond static data (coupon, day count, frequency, maturity, issue date, first coupon date) matches a canonical record — by comparing hashes, not by uploading the data.

The canonical record is built from cross-referenced public sources (multiple ETF holding files, where prospectus extraction confirms disagreements). The hash is published; the underlying values are not.

## Why it exists

Vendor-supplied bond static drifts from the issuer prospectus. A NAV pipeline, a recon process, or a portfolio analytics engine that consumes bad static produces bad output — accrued interest off by a day, yield off by basis points, duration off by tenths. The drift is silent until someone audits.

This project provides a way to check, on demand, whether the static you hold for a given ISIN agrees with what the prospectus says — without ever sending your data anywhere we can see it.

## How the trust model works

The protective property is **where the data flows**, not who wrote the code.

- The validator runs on **your** infrastructure: your laptop (local stdio), your Railway / AWS / GCP / on-prem container (recommended), or air-gapped with a daily signed snapshot. We have no admin access.
- Your bond static is hashed inside your network. The only thing that egresses is `GET /hash/{isin}` — a public ISIN, asking for our canonical hash.
- We have no API that accepts bond field values. The hash database is read-only by design; even a tampered validator could not exfiltrate to us, because no endpoint exists to receive your data.
- The source is here, MIT-licensed. Your security team can read it in an afternoon.

When your hash matches ours, you have cryptographic confirmation your static agrees with the canonical record. When it doesn't match, the validator tells you which field disagrees and points you at the public source (typically the prospectus URL) so you can verify and correct.

## What's in this repo (v0.1)

- [`SCHEMA.md`](SCHEMA.md) — the canonical schema spec: field list, JCS normalization, derivation rules for missing fields, tier hash construction
- [`examples/`](examples/) — golden test fixtures (canonical JSON + expected tier hashes for known bonds; populated alongside the reference SDK in v0.2)
- `LICENSE` — MIT

## What's coming next

- v0.2 — Python reference SDK with `validate_bond_static(isin, my_data)` and golden-test fixtures
- v0.3 — JavaScript SDK; cross-language byte-identical canonical-JSON CI harness
- v0.4 — Public read API (Cloudflare Worker), seeded with the first ~9k cross-referenced bonds
- v0.5 — Self-hosted container (Docker image on GHCR; one-click Railway template)
- v0.6 — MCP server wrapper for AI-agent workflows
- v1.0 — Ed25519-signed attestations, daily signed offline snapshots, Helm chart, Terraform module

See `SCHEMA.md` for the technical contract this all builds on.

## Contributing

Issues and discussion welcome. Pull requests for the schema spec are best raised as issues first; the spec needs to stay implementable byte-identically across languages, so any change is load-bearing.

## License

MIT. See `LICENSE`.
