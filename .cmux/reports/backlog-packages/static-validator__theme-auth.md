# static-validator / `theme:auth` — package report

**Lane:** `proposal/static-validator-theme-auth-10011132`  
**Slice:** item 1053 (the only open item supplied).  
**Code change:** none; the owning schema and database are in `bond_data_mcp`.  
**Tests:** none; documentation-only handoff, with no executable files changed.

## Underlying defects

The reported symptoms have two causes, both outside this repository:

1. `portfolio_uploads` and `portfolio_upload_evidence` permit anon access. The recorded live probe showed anonymous inserts and updates, so RLS/grant hardening belongs with the database owner.
2. `client_id` is free text and needs a stable FK target. The supplied disposition recommends a new `clients` table rather than mutable email, but that table and the wider Bucket D entitlement model are not defined here. Per-client RLS policies depend on that estate-level identity design.

This repo contains no code that reads or writes these tables. Its existing decision record, [.cmux/decisions/1053-tier2-upload-isolation.md](../../decisions/1053-tier2-upload-isolation.md), documents the live evidence and recommends enabling RLS without policies and revoking anon/authenticated writes before any client data is accepted. The existing `handoff-1053` report already carries an Andy decision card; this report repeats the machine-readable handoff for the current proposal but does not create a second decision card.

## Item disposition

- **1053 — not fixed here; hand off to `bond_data_mcp`.** Both database changes live with the owning Supabase schema. No change to this SDK's wire contract or client-facing financial values is warranted. The FK target and broader client-entitlement policy remain for the estate's Bucket D decision.

No other item ids were included in this package slice.

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: none
-->

<!-- lane-handoffs
item: 1053
repo: bond_data_mcp
change: In the owning bond-data migrations, harden public.portfolio_uploads and public.portfolio_upload_evidence: enable RLS and revoke anon/authenticated INSERT, UPDATE, and DELETE; then resolve the stable clients FK target and client-scoped policies as part of the Bucket D identity design. The recorded live probe found anonymous writes on both tables. Do not apply a migration from this repository.
-->
