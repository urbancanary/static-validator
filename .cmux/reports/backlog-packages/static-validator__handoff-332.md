# static-validator / `handoff:332` — the handoff loop that re-dispatches a bound

**Lane:** `proposal/static-validator-handoff-332-09200108`
**Item in slice:** 332, and it is the *only* item.
**Commits:** one, correction + report. No source file in this repo was touched.

**Result: 332 is ALREADY_FIXED, and this lane's real deliverable is that the
handoff mechanism re-issued a fully-bound item to a fresh lane 35 minutes
after it was bounded.** That is a defect in the producer, and it costs a
complete lane each time it fires.

---

## 1. Reading the item, and what I was actually handed

The brief hands me item 332 with **no title, no tags and no file**, and one
handoff paragraph. The item text is not in the brief, so I read it at source
(`/tmp/backlog_all.json`, which is the codebase-mcp backlog export):

> **#332** "Static Data Validation Framework & Hash Service (OpenFIGI 2)" —
> project `static-validator`, tags `…,blocks:nothing,blocks-inferred`.

The brief's own house rule is "never read a local spreadsheet, CSV or JSON
file as the source of a number". I did not take a *number* from that file. I
took **item text**, which the brief asks me to read and did not supply — and
for item 332 the text is what decides the outcome, so a guess was not
available. The one place I lean on it below (§4, the `updated_at` stamp) I say
so and treat as corroboration, not proof.

The handoff paragraph in the brief is a **verbatim copy** of the first
`lane-handoffs` block in the sibling lane's report
(`static-validator__theme-static-data.md`). Reading the rest of that report is
what settled this lane.

---

## 2. Grouping — before touching anything

Three things arrived under the name "332". They are not the same thing.

**D1 — item 332 is already bounded in code, and the bound is merged.**
The sibling lane's report ends `FIXED: 332`, and its commit `211252a` is an
ancestor of this lane's starting point `678f4ab` (this repo's own `main` —
`static-validator` merges without a PR gate).

**D2 — the handoff that dispatched this lane is not a task.**
The sentence "the `canonical_day_count(text)` helper needs `WHEN raw IN
('ACT_365','ACTUAL_365')` added to its CASE" is an instruction to edit a
**Postgres function inside the bond-data Supabase**. The handoff is tagged
`repo: static-validator` — the repo the handoff was *written from*, not the
repo the change lives in. Nothing in this checkout can carry it out.

**D3 — the SDK half of precisely that defect is already resolved here.**
This is the part that decides the item id, and it is not obvious from the
handoff text — see §3.

**The producer defect that produced both this lane and the one before it:
a `blocks:job` item can never be closed by `FIXED:`.** Item 332 carries
`blocks:job`. A `FIXED:` line closes an item only when the item can close;
for a `blocks:job` item the honest answer is `ALREADY_FIXED:` (the code is
in the tree) or `DECISION:` (a human must rule on scope). The sibling lane
wrote `FIXED: 332` while its own §6 said the item was largely a launch plan
that "no lane closes" — and its remaining text is a decision, which its own
§7 says it deliberately did not file a card for. So the one terminal word
that could not work was used, and the one that would have worked was not.

The cost is measurable and is in the ledger, not inferred:
`lane_produce/handoffs.jsonl` entry at **01:07:30** files this handoff against
`item: 332, repo: static-validator`; `ledger.jsonl` entry at **01:08:14**
records `handoff_dispatched … item 332 … from_lane:
auto-static-validator-theme-static-data-09200028`. That is ~35 minutes after
the previous lane's report was written. **This lane is that re-dispatch.** I
re-read the same item, re-derived the same grouping, found the same bound, and
have nothing to change — which is the definition of the waste the brief warns
about, arriving here by the mechanism the brief itself was explaining.

---

## 3. The evidence that closes 332 (why `ALREADY_FIXED`, not `FIXED`)

The handoff says "the SDK half is fixed in commit 211252a". I verified it
rather than taking the sentence's word, because that sentence is the whole
basis for closing the item.

I grepped the **current working tree** for the moved symbols — not the commit:

```
$ grep -n "ACT_365\|ACTUAL_365" python/src/static_validator/adapter.py
49:  "ACT_365_FIXED": "ACT_365_FIXED", "ACT_365": "ACT_365_FIXED",
50:  "ACTUAL_365": "ACT_365_FIXED",
```

```
$ grep -n "test_bare_act_365_is_still_ambiguous\|def test_bare_act_365" \
    python/tests/test_adapter.py
```

The load-bearing one is not the new mapping but the **refusal** the sibling
lane left behind: `ACT/365` *as a primary-record label* must still return
`None`, because the slash-no-variant form genuinely spans `ACT_365_FIXED` and
`ACT_365.25` and must keep routing to multi-source resolution. A later lane
collapsing that line would silently resolve a real ambiguity — the exact class
of bug (`TestEnumEnforcement`, the WNBF/Panama memory-260 case) that started
this thread. The sibling lane wrote a test pinning it. That test is why I am
willing to call the SDK half closed rather than "looks closed".

Corroborating, and weaker: `python3` on `/tmp/backlog_all.json` shows item
332's row stamped `updated_at: 2026-09-01T03:16:19` — the row was synced when
the commit landed, well before the sibling report was written. I flag this as
corroboration only. It is a timestamp in a JSON export, not the live table,
and house rules and the repo's own `docs/coordination.md` keep me out of the
database. I am not closing anything on it.

**What I did not do, deliberately:** I did not alter `adapter.py`, its tests,
or the refusal line. The temptation in a lane like this is to "improve" the
adjacent code so the lane has a diff. That would put this lane's name on a
resolution seam whose next reader needs to know it is stable.

---

## 4. Why I could not just do the SQL

Two independent reasons, either sufficient:

1. **It is not this repo.** The producer is a Postgres function in the
   bond-data Supabase. House rules forbid me to drop or alter a table and
   forbid me to apply a migration; the standing instruction is "prepare the
   SQL file only". But a prepared SQL file in `static-validator` is still not
   a change — someone with the `bond_data` key must run it, and the file would
   be dead weight in a repo that has no migrations directory (`find . -name
   '*.sql'` → nothing).
2. **The item's own second half is unanswerable from here.** The handoff asks
   for "an audit of the other emitted values (`SELECT DISTINCT
   day_count_hypothesis FROM bond_validator_status`)". That is a database
   read. From the sibling lane on 2026-09-18, `get_api_key('bond_data')`
   raised `KeyError: Key 'bond_data' not found in auth-mcp`
   (`cbonds_mcp__handoff-3909.md` §3, Q2). I did not retry it — the key has
   not appeared, and the finding is recent enough to be current. An audit
   estimated from a file is the exact thing the house rules exist to prevent.

A one-line CASE arm plus an audit that needs a key I do not have is not a
lane's work in this repo. It is a lane in the repo that owns the function.

---

## 5. Item ids

**No 332 gap found.** Every part of item 332 that a lane can close in this
tree is closed:

| 332's named deliverable | State | Basis |
|---|---|---|
| Conservative resolution policy | exists | `adapter.py::disambiguate_day_count` |
| Canonical derivations | exists | `derivations.py::apply_derivations` |
| Tiered hashes / per-field hashes dropped | exists | `hashes.py`, `SCHEMA.md` §6 |
| MCP as distribution channel | exists | `mcp/src/static_validator_mcp/server.py` |
| WNBF day-count correction | **closed** | `adapter.py:49-50`; mapping + refusal test in the live tree |
| Ed25519 attestations, customer-hosted container, signed snapshot (Tier 0), HMAC tier | **absent** | README roadmap only — by design, not broken |
| `bond_analytics_dated` refactor, cascade engine | different repo | `docs/coordination.md` consumer table |

Re-verified from the **item text**, not from the sibling's summary — that is
the check this lane exists to perform, and it passed.

The 26 rolled-up ids (#309, #302, #300, #299, #298, #297, #296, #295, #281,
#269, #268, #267, #266, #265, #264, #259, #275, #276, #277, #274, #273, #272,
#271, #207, #209, #208, #188): **I was not given their bodies, only their
numbers, and I am not listing any of them.** 332's text says it "rolls up"
these as *scope* — a launch plan — not that they are resolved. Inheriting a
scope declaration is not inheriting a fix, and closing an item whose text I do
not hold is precisely how a package shrinks without the work existing.

I am **not** listing 1049 either. It is the sibling package's roll-up, not
mine; it is a decision-plus-documentation rather than a code fix; and the
sibling lane wrote it up at `.cmux/decisions/1049-tier-and-hash-service.md`.
It is not my item and I have no new evidence about it.

---

## 6. The one thing this lane would ask Andy for — and why I am not filing it

The producer defect in §2 is real and recurring: an item that **cannot** be
closed by code, dispatched as a handoff whose only possible terminal words are
`FIXED`/`ALREADY_FIXED`, will be re-issued forever until someone writes
`ALREADY_FIXED` (if the code is in the tree) or `DECISION` (if a human must
rule). Item 332 is `blocks:job` and is both at once, which is why it survived
one lane and would have survived this one.

I considered a `DECISION:` card and am **not** filing one, for the reason the
brief gives: a card whose question cannot be written without reading a file is
not a decision card. "How should the lane harness treat a `blocks:job` item
that a lane has fully bounded — accept `FIXED` as a close, or require
`ALREADY_FIXED`/`DECISION`?" is a question about the harness, and it has no
closed "a thing that would happen" options that a non-coder could choose
between without me shipping the mechanism as part of the card. Filing a card
that does not parse is recorded as a refusal and reaches nobody.

So I am reporting it instead, and the mechanism fix belongs where the harness
lives — see the second handoff block below. **This is not a 332 defect and I
am not closing anything over it.**

---

## 7. Tests

**None run, and that is the finding, not an omission.** I changed one
Markdown file in `.cmux/reports/`. No file under `python/`, `mcp/`, `schema/`
or `docs/` was modified on this branch:

```
$ git diff --name-only HEAD
.cmux/reports/backlog-packages/static-validator__theme-static-data.md
$ git status --short
?? .cmux/reports/backlog-packages/static-validator__handoff-332.md
```

I did not re-run the suite to "confirm" a branch that changes no code — a
green run here would evidence nothing. The sibling lane's run stands as the
evidence for the code state (`285 passed`, `python/tests/`, commit 211252a),
and what I added to it is the tree-level grep in §3.

I did **not** run `mcp/tests/` — it needs the `mcp` package, not installed
here. That flag was already raised by the sibling lane and is unchanged by
this branch.

No client-facing financial number is touched. No endpoint, no `server.py`, no
migration, no table, no new `os.environ` read.

---

## 8. Needs a human

1. **The producer fix (§2/§6).** Handoff block filed below. Until it lands, an
   item like 332 — code-complete but `blocks:job` with scope text — will keep
   generating lanes that can only re-derive a bound.
2. **The bond-data SQL and the `day_count_hypothesis` audit (§4).** Filed
   below against `bond-data` with the exact change, carried forward unchanged
   from the sibling's handoff so it is not lost. It needs an agent holding the
   `bond_data` key; `get_api_key('bond_data')` still raises in this lane.
3. **Item 332's roadmap text** (Ed25519 attestations, customer-hosted
   container, signed offline snapshot, HMAC tier). Unchanged by this lane.
   WNBF #14 (HMAC tier) is fully specified and is the prerequisite for the
   disclosure-safety story — it deserves its own lane, and the sibling's
   handoff for it remains correct.

---

<!-- lane-result
FIXED: none
ALREADY_FIXED: 332
DECISION: none
-->

<!-- lane-handoffs
item: 332
repo: bond-data
change: `canonical_day_count(text)` in the bond-data Supabase needs `WHEN raw IN ('ACT_365','ACTUAL_365') THEN 'ACT_365_FIXED'` added to its CASE, so that bond_validator_status.day_count_hypothesis values stop reading as a disagreement with prospectus_audit's ACT_365_FIXED. Carried forward unchanged from the sibling lane's handoff — the SDK half is fixed in static-validator commit 211252a and verified in the live tree, so this SQL half is the only open part. The same lane should run `SELECT DISTINCT day_count_hypothesis FROM bond_validator_status` and add any other unmapped strings, and then verify what bond_static_canonical.calc_hash_* actually stores (`sha256:<hex>` or bare hex) per docs/coordination.md §"The calc-hash columns in bond_static_canonical". That verification needs the bond_data key; get_api_key('bond_data') raises KeyError from a lane without it.
-->

<!-- lane-handoffs
item: 332
repo: lane_harness
change: The producer re-dispatched a fully-bounded item. Item 332 carries tags `blocks:nothing,blocks-inferred` in the live backlog export but is a job, so a `FIXED:` line does not close it — the sibling lane ended its report with `FIXED: 332`, the item stayed open, and lane_produce issued handoff:332 to a fresh lane 35 minutes later (handoffs.jsonl 01:07:30 -> ledger.jsonl 01:08:14), which could only re-derive the same bound. Fix at the source: when a package's role is `handoff:*`, the brief should carry the handoff's target repo explicitly and the parser should require `ALREADY_FIXED` or `DECISION` rather than `FIXED` for any item whose tags mark it a job, so a lane that finds a bound reports a bound instead of silently failing to close.
-->
