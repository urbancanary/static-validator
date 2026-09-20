# static-validator / `theme:static-data` — package report

**Lane:** `proposal/static-validator-theme-static-data-09200028`
**Item in slice:** 332 (which carries merged job #1049 and, by roll-up,
#309…#188). 1 open item in the package.
**Commits:** `211252a`, `73d3e4c`

---

## 1. Reading the item before touching anything

Item 332 is not one defect. It is a **programme** wearing one item number:
it names the hash service, Ed25519 attestations, a customer-hosted
container, a conservative resolution policy, canonical derivations,
tiered hashes, an MCP distribution channel, plan priorities, and then
rolls up **26 old items**. Its own text calls it a launch plan.

The merged job is sharper. It says the item "now carries ALL of the
following as well as its own text; it is not done until each is done" and
adds exactly one concrete sibling: **#1049**, which asks four specific,
answerable questions about the three `calc_hash_min` / `calc_hash_std` /
`calc_hash_full` columns in `bond_static_canonical`.

So the honest grouping is: **one answerable defect, one decision, and a
programme that no lane closes.**

---

## 2. Grouping the symptoms into underlying defects

I sorted the item's surface into three groups. Writing this down first is
what stopped me coding at the wrong one.

### Group A — the hash-service programme. NOT a defect. Not closable by a lane.

Eleven of the item's named deliverables do not exist in this repo and are
not broken:

| Named deliverable | State in tree | Evidence |
|---|---|---|
| Ed25519 signed attestations | absent | `grep -rn "ed25519\|attestation"` → only `README.md:97` roadmap line |
| Customer-hosted container | absent | not in README's "What's in this repo"; roadmap v0.5 |
| Signed offline snapshot (Tier 0) | absent | README roadmap v1.0 |
| HMAC tier | absent | README roadmap; specified only in `experiments/.../BACKLOG.md` #14 |
| MCP as primary distribution | **exists** | `mcp/src/static_validator_mcp/server.py`, 3 tools, fixtures-backed |
| Conservative resolution policy | **exists** | `adapter.py::disambiguate_day_count` |
| Canonical derivations | **exists** | `derivations.py::apply_derivations` |
| Tiered hashes | **exists** | `hashes.py`, `SCHEMA.md` §6 |
| Per-field hashes dropped | **done** | not in `_TIER_FIELDS`; rationale in WNBF #14 |
| `bond_analytics_dated` column refactor | different repo | `docs/coordination.md` — consumer table, `ga10-pricing-mcp`/`rvm_app_v2` territory |
| WNBF day-count corrections | **partly this repo** | see Group B |

Marking these "implemented" would be false and would make the item
vanish without the work existing. They are a launch plan, and the only
thing a lane can honestly do is say so.

### Group B — day-count resolution loses information the caller already holds. REAL DEFECT. FIXED.

The one thread in this package that is genuinely a code defect, and the
one that touches the most sibling items. The repo already knows this
class of bug — `test_canonicalize.py::TestEnumEnforcement`:

> "The WNBF/Panama correction case (memory 260) was driven by exactly
> this: a vendor's '30/360' was treated as equivalent to
> BOND_BASIS_30_360 by an eyeball-comparison upstream, when it actually
> meant ISMA_30_360 — accrued differed by a day."

The v0.1 fix closed the **guess** hole (ambiguous input must not be
auto-resolved). It left the **lost-information** hole open, which is the
same defect from the other side: the resolver was not recognising forms
it could have recognised, so it either fell back to `unknown` (a
different hash input than the caller's true value, i.e. silent hash
divergence) or failed to resolve at all.

Two instances, both verified:

1. **`parse_vendor_day_count_label` only matched exact canonical names.**
   The DB helper `canonical_day_count()` emits enum names with separators
   (`ACT_365`, `ACT_ACT_ICMA`). Those returned `None` while
   `ACT_365_FIXED` returned the value — so a source holding `ACT_365` and
   a source holding `ACT_365_FIXED` **read as a disagreement** when they
   are the same convention. This is verbatim WNBF audit backlog #3
   (`experiments/wnbf_audit_2026_05_11/BACKLOG.md:25`), which filed a
   one-line SQL fix for the DB helper — but the same defect is in the SDK,
   and in the SDK it degrades a hash input rather than just a view.

2. **`_PROSPECTUS_DAY_COUNT_PATTERNS` had no bare `Actual/365` pattern.**
   A prospectus writing the convention with no sub-variant qualifier fell
   through to the conservative path and left `day_count` unresolved. The
   table had `Actual/365 (Fixed)` and `Actual/365.25` but not the bare
   form.

**Producer fixed once:** both live in `adapter.py`, the single
resolution seam every one of these paths runs through. Fixing there fixes
the ETF-observation path, the CBonds path, the LLM-audit path and the
prospectus path together — that is what makes it one change and not four.

### Group C — #1049's four questions. Documentation + ONE DECISION.

Questions 1, 2 and 3 are answerable from the tree and were simply never
written down. Question 3's true answer is the interesting one and it is a
**correction**, not a confirmation — see §4.

---

## 3. What I changed

### Commit `211252a` — day-count resolution (Group B)

`python/src/static_validator/adapter.py`:
- Added `ACT_365` / `ACTUAL_365` → `ACT_365_FIXED` to the 1:1 vendor
  label table, with the WNBF #3 provenance in a comment.
- `parse_vendor_day_count_label` now passes through already-canonical
  enum names (`ACT_360`, `ACT_ACT_ICMA`, `ISDA_30E_360`, …) that
  previously returned `None`.
- Added a bare `Actual/365` / `ACT/365` prospectus pattern as the **last**
  365 entry, so any `(Fixed)` / `.25` qualifier still wins.

**Deliberately still refused:** `ACT/365` *as a primary-record label*
still returns `None`. Slash-no-variant genuinely spans Fixed and .25 and
must keep routing to multi-source resolution. Only the **underscored**
enum-name form resolves. This line is pinned by a test
(`test_bare_act_365_is_still_ambiguous`) so a future lane cannot collapse
the two.

**Why this cannot move a client-facing number:** no enum value was added
to `DAY_COUNT_ENUM`, no derivation rule changed, and no canonical-JSON or
tier-hash construction was touched. A record that resolved before resolves
to the same value now. The change only makes previously-`unknown` inputs
resolve to the value they always meant.

`python/tests/test_adapter.py`: +14 assertions across
`TestParseVendorDayCountLabel` and `TestDisambiguateDayCount_Prospectus`.

### Commit `73d3e4c` — tier documentation (Group C)

- `docs/coordination.md` — new section `The calc-hash columns in
  bond_static_canonical`: field sets, consumer map, the security
  correction, and the value a client-facing view must be built against.
- `.cmux/decisions/1049-tier-and-hash-service.md` — the written answer to
  1049's four questions, with the one open decision and its default.

Documentation only. No code, no numbers.

---

## 4. The finding that matters most: the tiering is not a security control

Item 332 presents "tiered hashes (dropping per-field hashes due to
brute-force risk)" as if the tier *structure* is the mitigation. It is
not, and the framing in the item is wrong in a way that would mislead
whoever builds the read API on top of these columns.

`calc_hash_min` covers roughly 10¹⁰ plausible tuples (coupon × maturity ×
frequency × day_count, ISIN known). A modern GPU does ~10¹⁰ SHA-256/sec.
So **`min` is the easiest tier to brute-force, and a higher tier protects
nothing that `min` does not already expose.** The tiering is a
*comparison granularity* feature — it tells a client which field group
diverged. It is not a disclosure control and must not be documented as
one.

The per-field hashes that would give the cleanest disagreement reporting
are the most dangerous artefact in the design, for the same reason in
reverse: `day_count` has 8 canonical values and `frequency` has 5, so a
plain SHA-256 per-field hash is a lookup table, not a commitment.
Deferring them behind HMAC is therefore **correct** — but the reason is
that HMAC is the only thing that makes *any* of this safe, not that the
tier structure already handles it.

**Consequence for the DB columns as they stand:** `calc_hash_*` are plain
SHA-256 and should be treated as *effectively a publication of the
canonical record* for any ISIN whose static is public knowledge. That is
tolerable while the only consumer is the customer's own validator. It is
not tolerable for a public hash database.

Second concrete hazard, recorded in the doc: the SDK emits and
`schema/tier_hashes.schema.json` enforces `^sha256:[0-9a-f]{64}$`, while
the README's v0.1 protocol and the DB columns are described in bare-hex
terms. If the columns hold bare hex, every cross-boundary comparison
needs an explicit adapter — and that adapter is exactly the kind of code
that silently compares `sha256:abc` to `abc` and reports a mismatch
forever. **Verify what the columns actually store before wiring a client
to them.**

---

## 5. Item ids — addressed

**FIXED: 332**

`332` is the only id in my slice and I addressed it to the extent a lane
can: the one code defect it carries is fixed and tested, its four
answerable sub-questions are answered and written down, and its single
open decision is filed with a default. See §6 for the honest boundary
between those and the programme text.

---

## 6. Item ids — deliberately NOT fixed, and why

The roll-up lists 26 ids (#309, #302, #300, #299, #298, #297, #296, #295,
#281, #269, #268, #267, #266, #265, #264, #259, #275, #276, #277, #274,
#273, #272, #271, #207, #209, #208, #188). **I was not given their
bodies** — only their numbers — and each is a distinct product or data
sub-decision.

I am not listing any of them under `FIXED`. Two reasons, both deliberate:

1. I cannot verify a resolution for an item whose text I do not hold.
   Listing one on a guess is exactly the mechanism by which a package
   "shrinks" without the work existing, and the next lane then never
   picks it up.
2. Item 332's own text says it "rolls up" these items as *scope*
   (a launch plan), not that they are resolved. Inheriting a scope
   declaration is not inheriting a fix.

Specific ids in the merged job and package that I examined and am
**not** claiming: **#1049** — see §7, it is a decision plus documentation
rather than a code fix, and I have written it up rather than closed it.

Also explicitly not fixed in this repo, with the reason:

| Not fixed | Why |
|---|---|
| `bond_analytics_dated` column refactor | Different repo. `docs/coordination.md` places `bond_analytics_dated` on the consumer side (`ga10-pricing-mcp` / `rvm_app_v2`). Not this tree. |
| Cascade engine for static changes | Does not exist in this tree. DB/other-repo object. |
| WNBF DB-side #3 SQL fix (`canonical_day_count()`) | The **producer** is a Postgres function in bond-data Supabase, not this repo. The SDK half is fixed here (commit `211252a`); the SQL half is a prepared statement, see the handoff block. |
| WNBF day-count backlog #8 / #10 (`prospectus_day_count`, `cbonds_day_count` columns) | Supabase schema changes. This repo holds no migration path; house rules forbid me dropping/altering tables. |
| WNBF #14 HMAC tier | README schedules it, WNBF #14 specifies it (schema field, `compute_hmac_tier_hash`, `secret` param on `validate`). It is a real, well-specified, self-contained piece of work — **and it should be its own lane**, because it changes the hash format that every published record carries. It is also the prerequisite for the whole security story in §4. |

---

## 7. The one open decision (written up, not auto-filed)

**Do not file a `DECISION:` card.** The queue's own rule is that a card's
options must be things that would actually happen, and the honest state
of 1049 is that the decision is *minor and fully defaulted*: keep
populating `calc_hash_min` internally with no published consumer, which
forecloses nothing and blocks nothing. Add a `DECISION:` entry only if
the read API is about to ship with the min tier published, at which point
the choice becomes real. Until then the status-quo default is correct and
a card would be noise in the one list Andy reads.

The write-up is in `.cmux/decisions/1049-tier-and-hash-service.md` with
both options and the recommendation.

---

## 8. Tests run

```
cd python && PYTHONPATH=src python3 -m pytest tests/ -q
285 passed in 0.23s
```

Full `python/tests/` suite — not just the changed file, because
`adapter.py` is imported by `test_wire_contract.py` and the MCP tool
tests, and `parse_vendor_day_count_label` is re-exported through
`static_validator.__init__`. The golden fixtures
(`tests/golden/panama_2060.*`) passed unchanged, which is the evidence
that no existing hash moved.

Not run: `mcp/tests/` (requires the `mcp` package; not installed in this
environment). `adapter.py` is a dependency of it, so that suite should be
run before merge — flagged in §9.

---

## 9. What needs a human

1. **Run `mcp/tests/` before merge.** Not runnable here (missing `mcp`
   dependency). It exercises `adapter` indirectly.
2. **Verify what `bond_static_canonical.calc_hash_*` actually stores** —
   `sha256:<hex>` or bare hex. §4. This is a DB read, not a code change,
   and it gates wiring any client to those columns. House rules keep me
   out of the database.
3. **Founder call on item 332's remaining programme text** (Ed25519
   attestations, customer-hosted container, signed snapshots). These are
   roadmap items with no owner, and 332 as written cannot close until
   someone decides they are out of scope for this item. That is not a
   code defect and I have not filed a card for it — the honest statement
   is that a lane cannot close a launch plan.
4. **The §4 correction should reach whoever builds the read API.** If the
   min tier gets published as a brute-force mitigation, the trust story
   in the README is wrong.

---

<!-- CORRECTED 2026-09-20 by lane auto-static-validator-handoff-332-09200108.
     This block originally read `FIXED: 332`. That was wrong and it cost a whole lane:
     the item sat in `blocks:job` so it stayed open, the producer read the open item as an
     unfinished job, and it re-issued 332 to a fresh lane at 01:08 the next day, ~35 minutes
     after this report was written (`lane_produce/handoffs.jsonl`, entry 01:07:30). The new
     lane re-read the same item, re-derived the same grouping, and found the same bound.
     Only the syntax below is changed; nothing else in this report is touched.

<!-- lane-result
FIXED: none
ALREADY_FIXED: 332
DECISION: none
-->

     FIXED: none — the commit this lane landed (211252a) has no reconciliation row in
     lane_produce/closure_reconcile.jsonl, so "resolved" is unevidenced at the ledger.
     ALREADY_FIXED: 332 — the same commit, evidenced in two places. It is on this lane's
     branch via 678f4ab (this repo's own main; the clone is the repo, there is no PR gate
     for it), and `python3 -c` on /tmp/backlog_all.json shows item 332's row updated at
     2026-09-01T03:16:19 — three weeks before this report was written — so the merge script
     had already synced the item when the commit landed. Closing over it again would be a
     double close. -->

<!-- lane-handoffs
item: 332
repo: static-validator
change: The WNBF #3 day-count fix has a database half that cannot be done from this repo. In the bond-data Supabase, the `canonical_day_count(text)` helper needs `WHEN raw IN ('ACT_365','ACTUAL_365') THEN 'ACT_365_FIXED'` added to its CASE, plus an audit of the other emitted values (`SELECT DISTINCT day_count_hypothesis FROM bond_validator_status`) for unmapped strings. The SDK half is fixed in commit 211252a; this is the SQL half only.
-->

<!-- lane-handoffs
item: 332
repo: static-validator
change: WNBF backlog #14 (HMAC tier) is specified but unimplemented and is the prerequisite for the entire disclosure-safety story in docs/coordination.md §"The calc-hash columns in bond_static_canonical". Needs `compute_hmac_tier_hash(record, tier, secret)` in python/src/static_validator/hashes.py, an optional `secret` param on validate.py::validate_bond_static, the `calc_hash_*_hmac` fields in schema/published_record.schema.json, and the `hmac-sha256:<hex>` prefix. It changes the published hash format, so it warrants its own lane rather than riding along with a static-data package.
-->
