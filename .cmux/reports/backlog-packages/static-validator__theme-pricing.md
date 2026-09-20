# static-validator / `theme:pricing` — package report

**Lane:** `proposal/static-validator-theme-pricing-09200146`
**Item in slice:** 1043. 1 open item in the package.
**Commits:** none — nothing to change in this repo. A decision card, not a code fix.

---

## 1. Reading the item before touching anything

Item 1043 asks for an ETF-implied price fallback: when a client upload lacks
`PRICE` for some bonds, derive a synthetic price from the bond's weight in a
major EM/credit ETF (EMB, JPGB). The item is explicit that this is **not
blocking**, that **every realistic institutional upload includes prices**
(citing the State Street EWN portfolio of 2026-05-12), and that it should be
built **"once we see a real client upload that lacks prices"**. It also states
the v1 behaviour: **assume par for analytics + a visible flag**.

Two things in that text decide this lane:

1. The trigger condition is a *market observation* ("once we see a real client
   upload that lacks prices"). No lane can observe that; the actual client file
   is not in this repo. This is a parked question, not a symptom.
2. The v1 behaviour it describes — assume par, flag it visibly — does not exist
   in this tree at all. So if the trigger ever fires, there is nothing here to
   extend: the whole path is unbuilt.

---

## 2. Grouping the symptoms into underlying defects

One item, and it splits into exactly two separable things. Writing this down is
what stopped me coding.

### Group A — the ETF-implied price fallback itself. NOT a defect, NOT in this repo.

A price is not a member of the canonical field set this repo validates, and
cannot be. `SCHEMA.md` and `schema/published_record.schema.json` define a
`PublishedRecord` whose only value-bearing fields are `coupon`,
`maturity_date`, `frequency`, `day_count`, `issue_date`, `first_coupon_date`,
`calendar`, `business_day_convention`. Everything else on the record is
metadata: `tier_hashes`, `structural_flags`, `canonical_field_status`,
`sources`, `where_to_find`.

Price is deliberately outside that set, and correctly so: the hash protocol
exists to confirm *static structure* (does your day-count agree with the
prospectus), not valuation. A price that changed daily would make every tier
hash unstable and destroy the one property the validator sells. So "the
validator falls back to a price" cannot be read as "the hashing SDK gains a
price field" — it has to mean *the diagnostic pipeline above the SDK* handles a
missing price.

That pipeline is not in this tree:

- This repo is the SDK (`python/`), the MCP wrapper (`mcp/`), the schema and the
  spec. There is no upload parser, no portfolio path, no analytics step, no
  diagnostic renderer (`grep -rn "weight|holding|nav" python/src mcp/src` →
  three comment mentions of ETF holdings as *evidence sources*, no code).
- A fallback price is not an upload concern anyway. It is a **market-data**
  concern: it needs EMB/JPGB daily holdings + NAV, i.e. the work
  `docs/coordination.md` already assigns to the **`etf-scraper`** package
  (`mcp_central/etf-scraper/` → `bond_validator_evidence`), which the same doc
  flags as laptop-cron-bound and needing migration.

Writing an ETF-holdings fetcher, a weight-to-price model and an
assume-par-and-flag path into the *reference SDK* would be building a second,
unowned copy of `etf-scraper`'s job in the repo that is supposed to stay a pure
hashing reference. That is the wrong producer, and it also cannot be done
inside the house rules of this lane: a fallback price is a number a client
reads, and this lane may not introduce one.

### Group B — "assume par for analytics + visible flag". Not built here either.

Even the v1 half does not exist in this tree. `python/src/static_validator/`,
`mcp/src/static_validator_mcp/` and `schema/` contain no `price` field, no
`assumed_price` marker, no `is_price_assumed` flag, and no `structural_flags`
member for it (`structural_flags.schema.json` carries sinker/amortizing/
callable/putable/floater/step-up/step-down only). The flag the item asks for
belongs to whatever renders the diagnostic, not to the hash layer.

### The real finding: the flag has to live on the ATTRIBUTION axis, not the flag axis

This is the part worth Andy's attention, and it is why a code lane here would
have done damage.

The obvious implementation of "visible flag" is a new `structural_flags` entry,
e.g. `price_assumed_par: true`. That would be a mistake. `structural_flags`
answers **"does the customer's downstream engine need to handle something beyond
a vanilla bullet?"** — sinker, callable, amortizing, floater. Every consumer
that reads those flags does so to decide how to *price* the bond. A price that
was invented rather than observed is a different kind of statement: not *what
the instrument does*, but *where this number came from*.

The schema already has the right slot for it, and it is unused for price today:
`source_reference.schema.json` carries a `source_type` enum whose members
include **`etf_holding`**, plus `vendor_consensus` and `prospectus`. And
`canonical_field_status` carries a per-field `explicit | derived | default |
unknown` — the vocabulary that already means "we did not observe this, we
assumed it". So the honest design is:

- a fallback price is a **`source_reference` with `source_type: "etf_holding"`**
  (or `"derived"`), not a structural flag;
- an assumed-par price is a **`canonical_field_status: "default"`**, the value
  that already exists for exactly this meaning.

Attempting to file the flag under `structural_flags` would have typed the
attribution axis as a behaviour axis, and the first client engine that read
`price_assumed_par` as "handle this bond specially when pricing" would have
gotten it backwards.

---

## 3. What I changed

**Nothing. This is deliberate and it is the correct outcome for this item.**

I wrote no code, changed no schema, and opened no branch commit against
`python/`, `mcp/` or `schema/`. Reasons, in order of weight:

1. **The item is a parked question with its own trigger, not a defect.** Its
   text says build it "once we see a real client upload that lacks prices". No
   lane can see a client upload; the estate has to decide whether that condition
   has been met, or drop it. That is a decision card (§4).
2. **The producer is another repo.** The work belongs beside the portfolio
   upload path and the ETF holdings ingest (`etf-scraper`), not in the pure
   hashing SDK. Even the v1 half ("assume par + visible flag") has no home here.
3. **It would move a number a client reads.** A fallback price *is* a
   client-facing financial number. This lane's hard limit says stop and hand it
   back, and that is what this report does.
4. **Doing it in this repo would corrupt the thing this repo exists for.** Adding
   price to the validated field set would make the tier hashes unstable across
   days, which is the one property the validator sells.

Had I been given a trigger-free version of this item, the *only* defensible
change here would have been to reserve the attribution vocabulary above and
document it — and that is a schema change requiring a MAJOR version bump
(`canonicalize.py` header: any change to canonical serialization is breaking),
so it still is not this lane's to take unilaterally.

---

## 4. Item ids — addressed

**FIXED: none** — no code change was committed, so nothing is claimed as fixed.
**ALREADY_FIXED: none.**
**DECISION: 1043.**

---

## 5. Item ids — deliberately NOT fixed, and why

| Not fixed | Why |
|---|---|
| 1043 (as code) | Not closable in this repo. Price is not a canonical-validated field by design; the SDK cannot carry it, and the pipeline that could is the `etf-scraper` / portfolio-upload path, which does not exist in this tree. Handed off below. |
| 1043's v1 half ("assume par + visible flag") | Also absent from this tree, and belongs to the diagnostic renderer/upload path, not the hash layer. Same handoff. |

---

## 6. Tests run

```
cd python && PYTHONPATH=src python3 -m pytest tests/ -q
285 passed in 0.29s
```

Run as a baseline only — no file was modified, so no test's result is evidence
for a change. Stated here so the next lane knows the tree it is inheriting is
green.

---

## 7. What needs a human

1. **The trigger question in the card below.** Has a real client upload lacking
   prices actually been seen, or does 1043 stay parked? This is the whole of the
   item and only Andy (or whoever holds the client files) can answer it.
2. **The `etf-scraper` dependency is on a laptop cron.** `docs/coordination.md`
   already records this as needing migration to a cloud trigger. Any
   ETF-implied price work depends on it, so that migration is a prerequisite
   whoever builds this.
3. **If the fallback is ever built: put the provenance on the attribution axis.**
   `source_reference.source_type: "etf_holding"` plus
   `canonical_field_status: "default"` — not a new `structural_flags` member.
   See §2. This is a design constraint, not a bug, and it should reach whoever
   builds it.

---

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: 1043
-->

<!-- lane-decisions
item: 1043
question: Should the validator build an ETF-implied price fallback (EMB/JPGB weight-to-price) for client uploads that lack prices, or does 1043 stay parked until a real such upload arrives?
context: The item's own text gates the work on "once we see a real client upload that lacks prices", a market observation no code lane can make, and every realistic upload so far (State Street EWN, 2026-05-12) included prices.
option A: Keep 1043 parked; the standing v1 behaviour (assume par, flagged visibly) is the answer until a real incompletely-priced client upload is produced, and the item is re-opened only then.
option B: Commission the fallback now, as a scoped job in the ETF-scraper / portfolio-upload path (EMB/JPGB daily holdings + NAV to a synthetic price, with the price marked as assumed wherever it is shown) — not in the hashing SDK.
recommend: A
reason: The item says it is not blocking and every upload seen so far has prices, so building it now spends the ETF-holdings pipeline (currently a laptop cron) on a case that has not occurred.
default: A
-->
