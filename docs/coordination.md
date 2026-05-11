# Bond Static — Cross-Repo Coordination

**Status:** v0.1 — proposed architecture, captured 2026-05-11 during the
first WNBF prospectus-audit run. Some pieces are already wired (CBonds
ingestion, ETF scraper validator); some are aspirational (single daily cron
orchestrator, recurring TRACE check). This doc is the single reference for
how the four repos that touch bond static data are meant to interact.

---

## Why this doc exists

Four repos write into or read from bond static tables in the bond-data
Supabase (`xdgicslrdudsqlsudsgv`):

| Repo | Today's role | Cadence |
|---|---|---|
| `rvm_app_v2` | RVM regression + a one-off TRACE call-date fetcher | research; ad-hoc |
| `etf-scraper` | Daily ETF holdings + convention discovery + validator evidence | daily local cron |
| `ga10-pricing-mcp` | CBonds + QuantLib pricing, every-5-min pricing cron | 5 min |
| `static-validator` (this repo) | Prospectus audit + consensus + discrepancy + promote/revert | on-demand |

Without explicit coordination, each repo can silently overwrite another's
work, or duplicate effort, or leave a piece of the daily pipeline orphaned
(case in point: the TRACE call-date fetcher was a one-off and never
became recurring; ETF scraper local cron is laptop-bound and false-alarms
on weekends).

This doc names the actors, the data they own, the order they run in, and
the lock/revert pattern they must respect.

---

## The actor model

Every component is exactly one of three roles. Roles compose; a single
script must not play two.

### 1. Producers — write *evidence* with provenance

Producers populate columns or rows that carry a `*_source` field naming
themselves. They never silently overwrite another producer's output;
they go through the validator's promotion gate for fields they don't
own outright.

| Producer | Output | Provenance string convention |
|---|---|---|
| `etf-scraper` validator | `bond_validator_evidence`, `bond_validator_status` | implicit (table-bound) |
| `rvm_app_v2` TRACE fetcher | `bond_reference.call_date` + `call_date_source` | `trace_mcp_YYYY_MM_DD` |
| `static-validator` LLM audit | `bond_static_audit_findings` | `prospectus_audit:<run_id>` |
| CBonds ingester (lives in `ga10-pricing-mcp`) | `bond_reference.*`, `bond_cashflow_schedule` | `cbonds-confirmed` / `cbonds` |
| Admin reconciliation (manual / desk) | `bond_reference.conventions_source` | `admin-recon-empirical-YYYY-MM-DD` |
| Human override | various columns | `manual_<analyst>_<YYYY_MM_DD>` |

### 2. Validator — reconcile, surface disagreements, enforce safety

Exactly one component: `static-validator`. Owns:

| Table / View / Function | Purpose |
|---|---|
| `bond_static_audit_runs` | Run metadata for each LLM audit batch |
| `bond_static_audit_findings` | Per-bond LLM evidence, with trust class |
| `bond_static_field_sources` (view) | Per (isin, field, source) — every opinion |
| `bond_static_consensus` (view) | Per (isin, field) — modal value + consensus level (low/medium/high) |
| `bond_static_discrepancies` | One row per concrete actionable disagreement |
| `review_discrepancy(id, status, reviewer, notes)` | Single state-change for triage |
| `promote_discrepancy(id, promoter)` | Writes approved value to live, respects `locked` |
| `revert_promotion(id, reverter, reason)` | Restores `promoted_old_value` (planned) |

The validator **never directly modifies producer output**. It reads, it
flags, it promotes/reverts approved changes through the function gate.

### 3. Consumers — read live static

Consumers read `bond_reference` and `bond_cashflow_schedule` for calc
inputs. They must **never write to these tables**; their write target is
their own output table (`bond_analytics_dated`, holdings, NAV, etc.).

| Consumer | Reads | Writes |
|---|---|---|
| `ga10-pricing-mcp` QuantLib | `bond_reference`, `bond_cashflow_schedule`, prices | `bond_analytics_dated` |
| Athena display | `bond_reference`, `bond_identity` views | display only |
| Portfolio optimizer | `bond_reference`, holdings | optimizer output tables |

---

## The single daily-cron contract

**One trigger, one orchestrator, ordered sub-jobs with independent
fallbacks.** Lives in `ga10-pricing-mcp` (which already runs production
crons, has auth-mcp wiring, and is the closest thing to a daily
orchestrator today).

### Trigger

Daily 04:00 UTC (after most EM market close, before US open). One cron
entry in `wrangler.toml` calling `daily_static_refresh()`.

### Sub-jobs, in order

```
04:00 → 1. ETF scrape (currently in etf-scraper, MUST migrate off laptop cron)
            ↓ writes to bond_validator_evidence + bond_prices
04:10 → 2. Bond validator evidence aggregation → bond_validator_status update
            ↓ writes hypothesis_day_count / hypothesis_frequency / promoted_to_identity
04:15 → 3. TRACE call-date refresh (the recurring version of rvm_app_v2 one-off)
            ↓ writes bond_reference.call_date + call_date_source
            Trigger conditions (any of):
              - bond_reference.call_date IS NULL AND is callable
              - bond_reference.call_date < CURRENT_DATE
              - call_date_source IS NULL
              - conventions_updated_at < NOW() - INTERVAL '90 days'
            Restrictions: ISIN LIKE 'US%' (TRACE is US-only), locked = FALSE
04:25 → 4. CBonds static refresh (no change — already runs from ga10-pricing-mcp)
            ↓ writes bond_reference + bond_cashflow_schedule
04:30 → 5. static-validator audit on watchlist newcomers (NEW)
            ↓ writes bond_static_audit_findings for any ISIN that joined the
            ↓ watchlist since the last audit run; skips ISINs already audited
            ↓ in the last 30 days (idempotent)
04:50 → 6. Refresh bond_static_consensus + repopulate discrepancies
            ↓ (views are computed live, discrepancies need a daily INSERT job)
05:00 → 7. QuantLib analytics (no change — already runs)
            ↓ writes bond_analytics_dated
```

### Fallback rules

- Each sub-job is **independent**. A failure in step N does NOT abort
  steps N+1…N+M. Sub-jobs that depend on earlier output (e.g. step 7
  needs step 4) explicitly check the freshness of their input.
- Every sub-job writes a row to `job_log` (already exists in
  `ga10-pricing-db`) with `status ∈ {success, partial, failed, skipped}`
  and `notes`.
- If TRACE is unreachable (step 3), the day's static-validator audit
  (step 5) STILL runs — it just doesn't get the trace-derived call_date
  as a second source for newly-audited bonds.
- If the static-validator audit (step 5) fails or budget is exhausted,
  the QuantLib calc (step 7) still runs using existing static.

### Backstop monitoring

The smoke-test framework already monitors `bond_analytics_dated` row
freshness (the alerting framework we tripped earlier today). Add similar
probes for each sub-job's `job_log` table entry.

---

## Locks, provenance, and reversibility

This is the safety contract that lets multiple producers coexist.

### Locks

Two tables carry a `locked` flag (boolean, default FALSE):

- `bond_reference.locked` — when TRUE, no producer or promotion may
  modify static fields on this row.
- `bond_cashflow_schedule.locked` — same, per row.

(static-validator added a `locked` column to `bond_static_audit_findings`
too, for the same reason — parsers must not overwrite reviewed audit
rows.)

**Producers MUST honor the lock.** A producer writing a column without
checking `locked = FALSE` is a bug.

### Provenance strings

Every column that can be overlaid by multiple producers MUST carry a
`*_source` companion column. Existing examples:

| Live column | Provenance column |
|---|---|
| `bond_reference.day_count` | `bond_reference.conventions_source` (+ `conventions_updated_at`) |
| `bond_reference.call_date` | `bond_reference.call_date_source` |
| `bond_cashflow_schedule.redemption` | `bond_cashflow_schedule.source` |

Provenance strings follow the format `<producer>:<run_or_date>`. Examples
above. The static-validator framework reads these to attribute sources
in `bond_static_field_sources`.

### Reversibility

Two paths back from a bad overlay:

1. **Direct revert by provenance string** — for a whole-batch undo:

   ```sql
   UPDATE bond_reference
      SET call_date = NULL,
          call_date_source = NULL
    WHERE call_date_source = 'trace_mcp_2026_05_03';
   ```

   This works because every batch writes its provenance string into the
   `_source` column. No separate revert table needed for whole-batch undo.

2. **Per-row revert through the validator** — when an individual
   overlay was promoted through `promote_discrepancy()`, the function
   captured `promoted_old_value` on the discrepancy row. The planned
   `revert_promotion(id, reverter, reason)` function uses this to
   restore prior state with full audit trail.

**Implication for producers:** if you write a value that *overwrites* an
existing non-NULL value, route through `promote_discrepancy()` so the
old value is captured. If you only ever fill NULLs (like the TRACE
fetcher does today), direct writes are fine — the revert path is then
the batch-undo SQL above.

---

## Where each repo lives and what owns what

| Repo | URL | Owns | Does NOT own |
|---|---|---|---|
| `static-validator` | `mcp_central/static-validator/` | Audit schema, consensus views, discrepancy + review/promote/revert functions. **This doc.** | The actual prospectus PDFs (LLM fetches at run time). The recurring cron (lives in ga10-pricing-mcp). The bond_reference live data. |
| `ga10-pricing-mcp` | repo URL TBD — Cloudflare Worker | Daily cron orchestrator. CBonds → bond_reference / bond_cashflow_schedule. QuantLib analytics → bond_analytics_dated. TRACE call-date refresh (planned). | The audit/consensus layer (validator). |
| `etf-scraper` | `mcp_central/etf-scraper/` | ETF holdings + convention discovery → bond_validator_evidence, bond_validator_status. | The daily cron schedule (must migrate from laptop cron to cloud trigger via ga10-pricing-mcp). |
| `rvm_app_v2` | `xtrillion/rvm_app_v2/` | RVM regression, Hull-White OAS work, original TRACE one-off. | The recurring TRACE check (now belongs in ga10-pricing-mcp). |

---

## Open coordination questions

These are explicitly out of scope for v0.1 of this doc but should be
resolved before v1.0:

1. **Who owns the CBonds ingester code today?** The data flows in but
   the script's location is undocumented (likely inside `ga10-pricing-mcp`
   but worth a code search audit).
2. **Migrating etf-scraper off laptop cron** — needs a clean lift to
   either a Railway cron or a sub-job of the ga10-pricing-mcp daily cron.
   The false-positive smoke alerts we keep seeing are a direct symptom
   of the current setup.
3. **Static-validator audit budget** — at ~$0.30 per 30 bonds, auditing
   the full ~9k watchlist universe is ~$90 one-time, then ~$5/day for
   newcomers. Cheap, but worth a budget guard so a misconfigured loop
   can't burn through.
4. **Backfilling shadow-promotion records** for the 427 historical
   trace_mcp call_dates so they're revertable through the unified
   `revert_promotion()` function — required if we ever want to undo
   them via the framework rather than the batch-undo SQL.

---

## TL;DR for the cross-repo reader

- One daily cron, in `ga10-pricing-mcp`, runs everything in order with
  per-step fallbacks.
- Every producer stamps provenance into a `*_source` column.
- Every static-bearing table has a `locked` boolean that producers must
  honor.
- All multi-source decisions resolve through `bond_static_consensus`.
- All overlays of non-NULL values go through the validator's promote
  function so they're reversible.
- This doc is the contract. Update it when a new producer joins or a
  cadence changes.
