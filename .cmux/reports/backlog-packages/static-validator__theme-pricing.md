# static-validator / `theme:pricing` — package report

**Lane:** `proposal/static-validator-theme-pricing-09200336`
**Slice:** item 1043. 1 open item in the package.
**Commits:** none — nothing to change in this repo. The item is a decision, not a
repo defect.

This is the second lane issued against this item. The verdict is unchanged, and
this lane is short on purpose. What follows re-verifies the prior lane's claims
in the *current* tree rather than restating them, so the next lane can see the
evidence is live and does not re-issue the package a third time.

---

## 1. What the item actually asks for

> "When a client upload is missing PRICE for some bonds, fall back to a
> synthetic price derived from the bond's weight in a major EM/credit ETF (EMB,
> JPGB, etc. publish daily holdings + NAV). Not blocking for v1 — every
> realistic institutional upload (e.g. the State Street EWN portfolio reviewed
> 2026-05-12) includes prices. v1 behaviour for missing price: assume par for
> analytics + visible flag. Build ETF fallback once we see a real client upload
> that lacks prices."

Two independent things are fused in that paragraph, and they have different
owners. Separating them is the whole of this report:

- **the trigger** — "once we see a real client upload that lacks prices";
- **the body** — build an ETF-implied price fallback, or at minimum build the v1
  behaviour (assume par + a visible flag).

---

## 2. Grouping the symptoms into underlying defects

One item, no defect. There is exactly one symptom here and it is not a symptom.

### Group A — the ETF-implied fallback: not a defect, and not this repo

A price is not, and cannot be, a member of the field set this repo validates.
I re-verified this in the current tree rather than trusting the prior report:

```
$ grep -in "price" schema/*.json
(no output)
```

`schema/published_record.schema.json` carries only `coupon`, `maturity_date`,
`frequency`, `day_count`, `issue_date`, `first_coupon_date`, `calendar`,
`business_day_convention` as value-bearing fields; everything else is metadata
(`tier_hashes`, `structural_flags`, `canonical_field_status`, `sources`,
`where_to_find`). Repo-wide, the only `price` hits outside of prose are
`README.md:29` (an OMS export *contains* price — an input, not an output we
produce) and `docs/coordination.md:103` (a diagram arrow into `bond_prices`,
which `etf-scraper` writes, not this repo).

This exclusion is deliberate and load-bearing, not an oversight. The product is
a *static* hash: it confirms that your day-count agrees with the prospectus. Add
a daily-moving field to the canonical record and every tier hash becomes
unstable across days, which destroys the one property the validator sells.

So "the validator falls back to a price" cannot mean "the hash layer gains a
price field". It must mean the portfolio-upload / diagnostic pipeline handles a
missing price. **That pipeline is not in this tree.** This repo is the SDK
(`python/`), the MCP wrapper (`mcp/`), the schema and the spec — there is no
upload parser, no portfolio path, no analytics step, no diagnostic renderer.
And a fallback price is a market-data concern: it needs EMB/JPGB daily holdings
plus NAV, which `docs/coordination.md` already assigns to the **`etf-scraper`**
package (`mcp_central/etf-scraper/` → `bond_validator_evidence`), which the same
doc flags as laptop-cron-bound and needing migration.

Building an ETF-holdings fetcher, a weight-to-price model and an
assume-par-and-flag path into the reference SDK would be a second, unowned copy
of `etf-scraper`'s job — in the repo that is supposed to stay a pure hashing
reference. Wrong producer.

### Group B — the v1 half ("assume par + visible flag") is also not built here

I checked this specifically, because it is the half a code lane might be tempted
to "just do":

```
$ grep -rin "etf_holding\|assumed_price\|price_assumed\|is_price" python/src mcp/src schema
python/src/static_validator/wire.py:60:        "etf_holding",
schema/source_reference.schema.json:15:  "enum": [..., "etf_holding", ...]
```

Those two hits are the *existing provenance vocabulary*, not a price feature.
There is no `price` field, no `assumed_price` marker, no `is_price_assumed`
flag. `schema/structural_flags.schema.json` carries `is_bullet`, `is_sinker`,
`is_amortizing`, `is_callable`, `is_putable`, `is_floater`, `is_step_up`,
`is_step_down`, `has_make_whole`, `is_zero_coupon` — all instrument *behaviour*,
none of them attribution.

### The one finding worth carrying forward

The obvious implementation of "visible flag" is a new `structural_flags`
member, e.g. `price_assumed_par: true`. That would be wrong, and this is the
part that should reach whoever eventually builds the fallback.

`structural_flags` answers **"does the customer's downstream engine need to
handle something beyond a vanilla bullet?"** Every consumer reading those flags
does so to decide how to *price* the bond. A price that was invented rather than
observed is a different kind of statement: not *what the instrument does*, but
*where this number came from*. Typing the attribution axis as a behaviour axis
would make the first client engine that reads `price_assumed_par` handle the
bond specially when pricing — exactly backwards.

The schema already has the right slots, and they are unused for price today:

- a fallback price is a **`source_reference` with `source_type: "etf_holding"`**
  (already an enum member — `schema/source_reference.schema.json:15`, and
  already accepted by `wire.py:60`);
- an assumed-par price is a **`canonical_field_status: "default"`** — the value
  that already exists for precisely this meaning
  (`published_record.schema.json`: `explicit | derived | default | unknown`).

No new vocabulary is needed. That is a design constraint for the builder, not a
change this lane makes.

---

## 3. What I changed

**Nothing.** Deliberate. Four reasons, in order of weight:

1. **There is no defect.** The item's own text gates the work on "once we see a
   real client upload that lacks prices". That is a market observation. No code
   lane can make it, and the client file is not in this repo. This is a parked
   question, not a symptom.
2. **The producer is another repo.** The work belongs beside the portfolio
   upload path and the ETF holdings ingest, not in the pure hashing SDK. Even
   the v1 half has no home here.
3. **It would move a number a client reads.** A fallback price *is* a
   client-facing financial number. The lane's hard limit says stop and hand it
   back. That is what this report does.
4. **Doing it here would corrupt the product.** Adding price to the validated
   field set destabilises every tier hash across days.

Had this item arrived without its trigger, the only defensible change here would
have been to reserve the attribution vocabulary in §2 and document it — a schema
change requiring a MAJOR bump (`canonicalize.py` header: any change to canonical
serialization is breaking), so still not this lane's to take unilaterally.

---

## 4. Item ids — addressed

**FIXED: none.** No code change committed; nothing claimed as resolved.
**ALREADY_FIXED: none.**
**DECISION: 1043.**

---

## 5. Item ids — deliberately NOT fixed, and why

| Not fixed | Why |
|---|---|
| 1043 as a code fix | Not closable in this repo. Price is not a canonical-validated field by design; the SDK cannot carry it, and the pipeline that could is the `etf-scraper` / portfolio-upload path, absent from this tree. |
| 1043's v1 half ("assume par + flag") | Also absent from this tree, and belongs to the diagnostic renderer / upload path, not the hash layer. |
| 1043 as a handoff | Deliberately **not** handed off. `etf-scraper` is a package, not a backlog project name the handoff block accepts, and the item is explicitly gated on an event that has not occurred. Dispatching a building lane now would act on a trigger nobody has pulled. It is a decision first; the handoff follows if Andy picks option B. |

---

## 6. Tests run

```
cd python && PYTHONPATH=src python3 -m pytest tests/ -q
285 passed in 0.28s
```

Baseline only — no file was modified, so this is not evidence for a change. It
is stated so the next lane knows the inherited tree is green, and that the 285
figure is unchanged from the previous lane on this package.

---

## 7. What needs a human

1. **The trigger question (card below).** Has a real client upload lacking prices
   actually been seen, or does 1043 stay parked? This is the whole of the item
   and only Andy, or whoever holds the client files, can answer it.
2. **The `etf-scraper` dependency is on a laptop cron.** `docs/coordination.md`
   already records this as needing migration to a cloud trigger. Any ETF-implied
   price work depends on it, so that migration is a prerequisite whoever builds
   this — and it is worth doing on its own merits, since that doc also notes the
   cron false-alarms on weekends.
3. **If the fallback is ever built: put provenance on the attribution axis.**
   `source_reference.source_type: "etf_holding"` plus
   `canonical_field_status: "default"` — *not* a new `structural_flags` member.
   See §2. A design constraint for the builder, not a bug.

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
option B: Commission the fallback now as a scoped job in the ETF-scraper / portfolio-upload path (EMB/JPGB daily holdings + NAV to a synthetic price, with the price marked as assumed wherever it is shown) — not in the hashing SDK.
recommend: A
reason: The item says it is not blocking and every upload seen so far has prices, so building it now spends the ETF-holdings pipeline (currently a laptop cron) on a case that has not occurred.
default: A
-->
