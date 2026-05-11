# WNBF Audit Run — 2026-05-11

First end-to-end run of the prospectus-static audit pipeline against the
WNBF (Wealthy Nations Bond Fund) holdings universe (30 bonds).

## Goal

Establish whether Gemini Pro + Google Search grounding can produce
prospectus-quoted evidence for bond static (day-count, principal repayment,
call optionality) at a quality level acceptable for the static-validator
canonical record.

## Pipeline

```
WNBF holdings (30 ISINs from bond-data Supabase)
        │
        ▼
harness_v2.py / harness_v3.py        ← gemini-3.1-pro-preview + googleSearch
        │  (parallel, 6 workers, ~10 min)
        ▼
v2_results / v3_results JSON         ← raw LLM responses
        │
        ▼
parse_to_canonical.py                ← extracts structural fields, derives trust class
        │
        ▼
v{2,3}_canonical.json
        │
        ▼
load_to_supabase.py                  ← POST to bond_static_audit_findings via PostgREST
        │
        ▼
bond-data Supabase
  ├── bond_static_audit_runs        (run metadata, 1 row per run)
  ├── bond_static_audit_findings    (per-bond LLM evidence, 30 rows per run)
  └── bond_static_discrepancies     (concrete field-level disagreements, ~19 rows per run)
        │
        ▼
review_discrepancy(id, status, ...)  ← human triages
        │
        ▼  (status='approved' rows)
promote_discrepancy(id)              ← (FUTURE) writes to bond_reference / bond_cashflow_schedule
```

## Versions in this dir

| File | Purpose |
|---|---|
| `descriptors_clean.json` | Per-bond descriptors: openfigi_ticker + bond_identity.issuer + figi |
| `harness_v2.py` | First successful run. Used clean descriptors. Run id `wnbf_2026_05_11_v2` |
| `harness_v3.py` | v2 + day-count disambiguation rule in the prompt. Fixes US-convention bias on Reg S Eurobonds. Run id `wnbf_2026_05_11_v3` |
| `parse_to_canonical.py` | Parses raw LLM prose into structured fields (day_count_class, principal_repayment, par_call, MW spread). Also computes trust_class. |
| `load_to_supabase.py` | POSTs canonical rows to bond_static_audit_findings via PostgREST. |
| `reparse_amortization.py` | Second-pass: pulls amortization schedule from the B2 block of raw_text only (avoids the par-call date leak that the initial parser had). Respects `locked = FALSE`. |
| `reparse_principal.py` | Second-pass: fixes principal_repayment classification with negation-awareness and first-sentence priority. Respects `locked = FALSE`. |
| `v2_canonical.json` | Canonical v2 dataset (30 rows). |

## Findings — short version

- 15/30 bonds got `high_prospectus_quoted_with_chunks` trust on v2.
- 4/30 flagged AMORTIZING (Panama 2047, Panama 2060, Galaxy, Greensaif). After reparse: Panama 2047/60 with full schedules; Galaxy/Greensaif partial.
- 19 discrepancies populated against bond_reference / bond_cashflow_schedule:
  - 3 HIGH: Panama 2047 cashflow amount mismatch (CBonds 31.75/31.75/36.51 vs prospectus 33.33/33.33/33.33)
  - 7 medium: par-call dates missing from bond_reference (clean additions)
  - 9 medium/low: day_count noise — LLM US-convention bias mis-classifying Reg S Eurobonds. **v3 prompt fixes this.**

## Reproducing the run

```bash
export GEMINI_API_KEY=<from auth-mcp>
python3 harness_v3.py                          # ~10 min wall clock
python3 parse_to_canonical.py                  # local
python3 load_to_supabase.py                    # writes to Supabase
# Then in SQL:
#   - populate bond_static_discrepancies from this run
#   - review via review_discrepancy(id, status, reviewer, notes)
```

## What's intentionally NOT here

- The Anthropic / OpenAI API keys (sourced from auth-mcp at runtime).
- The actual prospectus PDFs (sourced live by Pro+grounding).
- Any code that writes to live `bond_reference` / `bond_cashflow_schedule` — that path goes through `promote_discrepancy()` and only on `status='approved'` rows.
