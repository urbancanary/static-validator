# 1043 — Missing prices: the validator owns provenance, not price

**Status:** the code half is recorded here; one decision is outstanding.
**Owner question:** has a real client upload lacking prices actually been seen?
**Blocks:** nothing. Not blocking for v1, and the item says so.
**Related:** item 1049 and item 1053 (this repo's decision-record pattern),
item 1046 (the Tier 2 service has no code in any checkout here).

This file is written because item 1043 has now been issued to **three** lanes
and all three reached the same verdict without producing anything the next
reader could start from. The package is re-issued because the item looks like a
code fix. It is not one. What follows separates the part that is settled by
reading code from the part only Andy can settle, so the next reader starts from
this instead of re-deriving it a fourth time.

---

## 1. The item bundles two things with different owners

> "When a client upload is missing PRICE for some bonds, fall back to a
> synthetic price derived from the bond's weight in a major EM/credit ETF …
> v1 behaviour for missing price: assume par for analytics + visible flag.
> Build ETF fallback once we see a real client upload that lacks prices."

- **the trigger** — "once we see a real client upload that lacks prices";
- **the body** — build an ETF-implied fallback, or at minimum the v1 behaviour.

The trigger is a market observation. No lane in this repo can make it: the
client file is not here, and neither is any code that would read one.

## 2. A price cannot be a field this repo validates — verified

```
$ git grep -in price origin/main -- schema
(no output)

$ git grep -in price origin/main -- python mcp
python/tests/test_gemini_extractor.py:39:  ... a redemption price equal to 100% ...
(one prose fixture; not a field)
```

`schema/published_record.schema.json` admits exactly eight value-bearing fields
into `canonical_field_status`, with `additionalProperties: false`:

```
^(coupon|day_count|frequency|maturity_date|issue_date|first_coupon_date|calendar|business_day_convention)$
```

Price is not among them, and that is load-bearing rather than an oversight.
`SCHEMA.md` §8 line 167 states it in the spec's own words: *"**Pricing or
analytics** (yield, duration, OAS, spread) — these are computations, not
static."* The product is a **static** hash. Add a daily-moving field to the
canonical record and every tier hash becomes unstable across days, which
destroys the one property the validator sells.

So "the validator falls back to a price" cannot mean the hash layer gains a
price field. It must mean the portfolio-upload / analytics pipeline handles a
missing price — and **that pipeline is not in this tree**. This repo is the SDK
(`python/`), the MCP wrapper (`mcp/`), the schema and the spec:

```
$ git grep -rln 'upload\|portfolio' origin/main -- python mcp schema
(no matches)
```

No upload parser, no portfolio path, no analytics step, no diagnostic renderer.
Note the asymmetry with item 1053: there, the absence was verified *outside*
this repo too — the `bond-data` tables and the audit document exist somewhere.
Here, the consumer of a fallback price is an ET L step that no repository on
this host contains, and `docs/coordination.md` assigns the market data it would
need (EMB/JPGB daily holdings + NAV → `bond_prices`) to **`etf-scraper`**,
which the same doc records as a laptop cron that must migrate. A fallback price
is a **market-data** concern. Its producer is `etf-scraper` (in
`mcp_central`), not this SDK.

Both halves of the body are therefore homeless here — the ETF fallback *and*
the v1 "assume par + visible flag", which belongs to the renderer that would
show the flag.

## 3. The half that lives here, and nobody had written down

The one part of 1043 this repo *does* own is the shape of the answer: how a
price that was assumed rather than observed is allowed to be represented. Two
designs are available and one of them is a trap.

**The trap.** The obvious "visible flag" is a new `structural_flags` member,
e.g. `price_assumed_par: true`. This would be wrong. `structural_flags`
answers *"does the customer's downstream engine need to handle something beyond
a vanilla bullet?"* Every consumer reading those flags does so to decide how to
**price** the bond — `is_callable` even carries the instruction "Yield-to-worst
should be used in place of yield-to-maturity" (`SCHEMA.md` §10). A price that
was invented rather than observed is a different kind of statement: not *what
the instrument does*, but *where this number came from*. Typing the
attribution axis as a behaviour axis would make the first client engine that
reads `price_assumed_par` handle the bond specially when pricing — exactly
backwards. The flag set is also `additionalProperties: false` with
`required: ["is_bullet"]`, so a new member is a wire change for every consumer.

**The right slots already exist, and are unused for price today:**

- an **ETF-implied** price is a `source_reference` with
  `kind: "etf_holding"` — already an enum member
  (`schema/source_reference.schema.json:15`) and already mirrored in
  `python/src/static_validator/wire.py:60`, so it is already legal wire;
- an **assumed-par** price is `canonical_field_status: "default"` — the value
  that exists for precisely this meaning, with `where_to_find` beside it for
  the "here is where to get a confirmed value" hint
  (`schema/published_record.schema.json`).

This is a **design constraint for whoever builds the fallback**, not a change
this lane makes. No new vocabulary is needed anywhere in the estate.

## 4. Why this lane is not making a code change

1. **There is no defect.** The item's own text gates the work on an event that
   has not occurred. "Not blocking for v1" is in the item.
2. **Neither half has a home here** (§2).
3. **A fallback price is a client-facing financial number** — a price on a page
   a client reads. The lane's hard limit says stop and hand it back for
   independent Claude review. This is that hand-back.
4. **Doing it here would corrupt the product** (§2, tier hashes).
5. **Even the tempting schema reservation is not this lane's to take.**
   Reserving `default` as the assume-par marker is already legal; going further
   and adding a price field would be a MAJOR version bump
   (`python/src/static_validator/canonicalize.py` header: any change to
   canonical serialization is breaking).

## 5. What this lane changed

One file, and it is this one. `.cmux/decisions/` is the right home for a
documented decision in this repo — item 1049's record established it,
`1053-tier2-upload-isolation.md` is the second — and committing it beside the
code means the next lane reads it instead of re-reading the item and reaching
the same verdict for the third time.

## 6. What a builder must do, if the fallback is ever commissioned

Stated so it does not have to be re-derived, and so the trap in §3 is not
walked into:

1. Build it in the **portfolio-upload / `etf-scraper` path**, not in
   `static-validator`. This repo has no upload path to put it in.
2. Mark the price on the **attribution** axis:
   `kind: "etf_holding"` for an ETF-implied price, `default` for assume-par.
   Never a new `structural_flags` member.
3. Do not add price to `canonical_field_status`'s pattern or to any hash input.
4. The ETF-scraper dependency is a **laptop cron** that
   `docs/coordination.md` already records as needing migration. Any ETF-implied
   price depends on it, so that migration is a prerequisite.
5. Andy's standing rule applies: a fallback price is a client-facing financial
   number, so it takes independent Claude review before it lands.

## 7. What is NOT in dispute

- The v1 shortcut (assume par + a visible flag) is **intentional** and stated
  in the item. Nothing has regressed; no test is red because of this.
- Every upload observed so far carried prices, including the State Street EWN
  portfolio of 2026-05-12 that the item names.
- This item blocks nothing in this package or any other.
