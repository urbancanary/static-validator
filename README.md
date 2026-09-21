# static-validator

A free, open toolkit for diagnosing bond static data quality — by what your system produces, not by inspecting what your system stores.

**Status:** v0.2 (evolving). v0.1 published a schema spec and a hash-only protocol for paranoid clients. v0.2 expands the project in light of real OMS exports: it turns out we can tell a great deal about a customer's static-data quality from just their reported analytics (accrued interest, yield, duration), without them uploading the underlying static fields. The schema and hash protocol from v0.1 remain stable; the application layer above them is the part still moving.

---

## What this is

A toolkit that answers: **"Is the bond static data driving your portfolio analytics correct, and if not, where is it broken?"**

Three deployment tiers share the same codebase, differing only in how much trust the customer places in us:

| Tier | Where it runs | What we see | Who it's for |
|---|---|---|---|
| **0 — Air-gapped** | Your infrastructure | Nothing — even reference data is a daily signed offline snapshot | Banks, sovereigns, paranoid quant desks |
| **1 — Self-hosted with read API** | Your infrastructure | ISINs only, via outbound `GET /bond/{isin}` calls | Security-conscious mid-market |
| **2 — Hosted convenience** | Our infrastructure at `validator.x-trillion.com` | The portfolio you upload, under explicit terms of service | Users who want zero operational overhead |

In every tier the diagnostic answer is the same. Tier 0 trades convenience for cryptographic guarantees. Tier 2 trades guarantees for convenience.

---

## The key insight (v0.2)

Most clients assume that to audit their bond static, they have to upload it. They don't.

A typical OMS export already contains everything we need to diagnose static quality: ISIN, coupon, maturity, price, **the customer's reported accrued, YTM, and modified duration**. From those outputs alone, we can determine:

- **House conventions.** Which day-count and settlement convention the back office uses — fitted from the median of all reported accrueds across the portfolio.
- **Calc-engine gaps.** Where the OMS gave up silently — YTM reported as 2.39 × 10⁻⁵, duration null, current yield computed on the wrong basis.
- **Silent misclassifications.** Project-finance bonds tagged as vanilla `Bond` when our reference shows dozens of redemption events. The customer's reported yield matches our bullet model exactly — so we know their system is pricing them as bullets — but the bonds are amortizers, and their numbers are wrong.
- **Static drift against canonical.** Per-ISIN comparison against the reference data set whose hashes are published in this repo.

None of these findings require the customer to upload day-count, frequency, sink schedule, or call schedule. **Their outputs are diagnostic enough.**

---

## Why this exists

Vendor-supplied bond static drifts from the issuer prospectus. NAV pipelines, recon processes, and portfolio analytics engines that consume bad static produce bad output — accrued off by a day, yield off by basis points, duration off by tenths. The drift is silent until someone audits.

Most institutional desks use a data feed (BBG, Refinitiv) plus an OMS (MAIA, Wayside, Epic, Alpha Desk). The feed delivers data; the OMS consumes it. Static errors hide in the gap between them — especially for amortizing and callable bonds, where the OMS calc engine either gives up silently or pretends the bond is a vanilla bullet. We've seen this on real client files.

This validator surfaces those errors. In Tier 0, it does so without your data ever leaving your network.

---

## How the trust model works

The protective property is **where the data flows**, not who wrote the code.

### Tier 0 — air-gapped

- The validator runs on your infrastructure: your laptop (local stdio), your Railway / AWS / GCP / on-prem container, or fully offline.
- The hash database is delivered as a daily signed offline snapshot. The validator makes **no network calls** during a run.
- The MIT-licensed source is here. Your security team can read it in an afternoon.
- When your hash matches ours, you have cryptographic confirmation your static agrees with the canonical record. When it doesn't, the validator tells you which field disagrees.

### Tier 1 — self-hosted with read API

- The validator runs on your infrastructure. **Your portfolio data never leaves your network.**
- During a run, the app makes outbound `GET /bond/{isin}` calls to our public read API to fetch enriched reference data. The read API is `GET`-only and accepts no bond field values — even a tampered validator binary could not exfiltrate to us, because no endpoint exists to receive your data.
- A subscription to our enriched-data service gates which fields the read API returns (sink schedules, NFA ratings, prospectus citations). The app code is identical regardless of subscription tier.

### Tier 2 — hosted convenience

- You upload the portfolio file to `validator.x-trillion.com`. We process it on our infrastructure.
- We see your data. Terms of service make that explicit. We retain it for history and shareable URLs; you can delete it.
- This is the convenience option, not the security option. If you have a data-residency or compliance reason to avoid sending portfolio data to a vendor, use Tier 1 instead.

---

## What's in this repo

- [`SCHEMA.md`](SCHEMA.md) — canonical schema spec: field list, JCS normalization, derivation rules, tier hash construction, structural metadata flags
- [`schema/`](schema/) — schema JSON examples
- [`python/`](python/) — reference Python SDK with golden test fixtures (`pip install -e .` from `python/`)
- [`mcp/`](mcp/) — MCP server wrapper
- [`examples/`](examples/) — canonical JSON examples for spec readers
- [`experiments/`](experiments/) — research workspaces (WNBF audit, prospectus extraction)
- `.claude/skills/validate-portfolio/` — orchestration skill for the diagnostic pipeline; same code serves all three tiers via config flags
- `LICENSE` — MIT

The schema applies to **every fixed-rate bond**, not only vanilla bullets. Structural complexity (sinkers, callables, floaters) is communicated via metadata flags published alongside the tier hashes — see SCHEMA.md §10. A customer matching `calc_hash` knows the static fields agree; the structural flags tell them whether their downstream engine needs to handle anything beyond a vanilla bullet.

---

## What's coming next

- **v0.2 (current)** — `validate-portfolio` skill: OMS-export parser (starting with State Street), QuantLib analytics, convention inference, Athena-style diagnostic HTML
- **v0.3** — Public read API (Cloudflare Worker), seeded with the first ~9k cross-referenced bonds; subscription gates enriched fields
- **v0.4** — JavaScript SDK; cross-language byte-identical canonical-JSON CI harness
- **v0.5** — Self-hosted container (Docker image on GHCR; one-click Railway template) for Tier 1 deployment
- **v0.6** — Tier 2 hosted at `validator.x-trillion.com`; portfolio history; shareable URLs. Tier 2 stores what you upload, so it ships behind an isolation boundary: server-side identity for every upload, plus database access rules so no caller can read another client's portfolio. See `.cmux/decisions/1053-tier2-upload-isolation.md`.
- **v1.0** — Ed25519-signed attestations, daily signed offline snapshots for Tier 0, Helm chart, Terraform module

The schema (SCHEMA.md) is stable enough to design against; expect minor revisions before v1.0.

---

## Contributing

Issues and discussion welcome. Pull requests for the schema spec are best raised as issues first; the spec needs to stay implementable byte-identically across languages, so any change is load-bearing.

## License

MIT. See `LICENSE`.
