# static-validator / `theme:pricing` — package report

**Lane:** `proposal/static-validator-theme-pricing-10041102`
**Slice:** item 1043 (the only open item in this package).

## Grouping (step 2)

This package contains one item, and 1043 is not two things wearing one number —
it is **two things with two different owners**, and only one of them is a
question:

- **the trigger** — "once we see a real client upload that lacks prices". A
  market observation. No lane can make it; the client file is not in this repo
  and there is no code here that would read one.
- **the body** — build an ETF-implied price fallback, or at minimum the stated
  v1 behaviour (assume par + a visible flag). A build, belonging to the
  portfolio-upload / `etf-scraper` path, gated on the trigger.

So there is exactly **one underlying fact** behind this package: *the fallback
is gated on an event the estate has not observed*. That fact is not a defect and
cannot be fixed by code in any repository. It is the whole package.

## The item's premise, re-verified in this tree (not re-derived from the item)

I confirmed the screened line rather than trusting it, as the brief asks:

```
python/src/static_validator/wire.py:60:        "etf_holding",
```

It is still there, and it is still **provenance metadata**, not an
implementation site: it is one member of `SourceReference.kind`
(`wire.py:55-68`), mirrored by `schema/source_reference.schema.json`. An
ETF-implied price is expressible on the *attribution* axis today with **zero**
changes — the vocabulary exists; nothing consumes it for a price.

I re-confirmed the two load-bearing facts the prior disposition verified, in
this clone:

```
$ grep -n "canonical_field_status" -A 12 schema/published_record.schema.json
  patternProperties: ^(coupon|day_count|frequency|maturity_date|issue_date|
                        first_coupon_date|calendar|business_day_convention)$
  "additionalProperties": false

$ grep -rln "portfolio\|upload" python/src mcp
(no matches)
```

Price cannot be added to the canonical record without destabilising every tier
hash across days — the one property the product sells. And there is no upload
parser, portfolio path or diagnostic renderer here for a fallback, or for its
"visible flag", to live in. `.cmux/decisions/1043-price-provenance-not-a-validated-field.md`
already records this in full; I am not restating it, I am confirming it still
holds.

## What this lane found that the previous four did not

Four lanes have now been sent at 1043 and none of them produced a durable
outcome. **The reason is not the item. It is that this package is parked on a
decision card that does not exist** — the previous lane wrote a correct card,
and the estate then lost it.

Measured, from the merge ledger at `/opt/work/lane_merge/ledger.jsonl`:

- `auto-static-validator-theme-pricing-10030654`, **2026-10-03T07:04:02+00:00**,
  verdict `merged`, records:

  ```
  raised_items: {"raised": [{"id": 1043, "card": "D277",
                  "covers": [1043], "question": "Should the ETF-implied price
                  fallback remain parked until a real client upload without
                  prices appears, or should the work be commissioned now?"}],
                 "skipped": [], "failed": []}
  ```

  i.e. the card written for this package **was filed, as D277, with no skip and
  no failure**.

- D277 is **absent from the live queue**.
  `/opt/work/mcp_central/ANDY_DECISION_QUEUE.md` carries 45 open cards, topping
  out at **D271**; the high-water marker reads
  `<!-- ANDY-QUEUE:ISSUED-TO D271 issued 2026-10-04T06:52:23+00:00 -->`;
  `grep D277` over the whole file returns nothing. Every D272–D284 raised
  between 2026-10-02T07:42 and 2026-10-03T09:02 is absent; only D272/D273/D274/
  D275/D279/D280/D281/D284 replaced themselves under fresh ids later.

- **This is not a D277 problem.** Of the 27 cards the ledger records as raised,
  **12 were raised and never filed** (D273, D277, D278, D282, D272, D274, D275,
  D279, D280, D281, D283, D284). (D272 lost one card and re-minted the id for a
  different question.) 15 survive. In 16 hours on 2026-10-02/03 the route filed
  12 cards and lost all 12.

- There **is** a durable home that would have caught this — the queue's settled
  log (214 `### ANSWERED` headings, retained by `andy_queue.answer`) — but a
  *filed* card is not written there, and a card that is **never filed** leaves no
  trace anywhere in mcp_central: `grep -rl D277` over `/opt/work/mcp_central`
  returns nothing. The merge ledger outside the repo is now the only record that
  this package was ever carded at all.

**Consequence, and it is the reason this package is the size it is.** Because
the raise is sticky by lane (`lane_produce.dispatchable_packages` reads
`merge_raised` over the *whole ledger*) but the park requires the card to be
findable in the live queue (`CARD_PACKAGE_RE` over `andy_queue.open_items()`),
the two halves disagree the moment a card is lost. The estate is now in the
state where **no new card can park this package and the lost card cannot park it
either** — so `static-validator theme:pricing` is re-issued every 20 minutes,
forever, to a lane that can only ever reach a fifth verdict identical to the
first four. That is the "days go by and nothing happens" the brief opens with,
manufactured mechanically by a failed write.

I am **not** re-filing a card for 1043. A card whose default is "do nothing"
adds no information; the estate is already defaulting to it, and it would burn
another D-id to say so. Filing one would also make the package *look* settled
while the question stays unasked — the exact failure mode the brief warns about.
The defect that needs a human is upstream of the card.

## Item accounting

- **1043 — DECISION, and not mine to close.** The question — *has a real client
  upload lacking PRICE been seen, and is the ETF-implied fallback commissioned
  or not?* — is unanswerable from this repository and already recommended KEEP
  PARKED by disposition batch `20260921-13` (rA). Its previous lane put that
  question on Andy's desk correctly and it was lost in transit. Recommend:
  keep parked. **If** the answer is "build it", the work belongs in the
  portfolio-upload / `etf-scraper` path after that pipeline's recorded
  laptop-cron migration, marking the price as `kind: "etf_holding"` (ETF-implied)
  or `canonical_field_status: "default"` (assume-par) — never a new
  `structural_flags` member, and never a price field in the hash input.

No other item ids are in this package, so there are none to leave undone.

## Why no code changed here

1. There is no defect in this repository. The item's own text gates the work on
   an event that has not occurred, and calls it not blocking for v1.
2. Neither half of the body has an implementation site here (verified above).
3. A fallback price is a **client-facing financial number**, so the hard limit
   applies: write it up, do not touch it. This is that write-up.
4. Building it in `static-validator` would put a daily-moving field into the
   canonical record and destabilise the tier hashes — it would corrupt the
   product rather than fix it.

## Tests

No code changed, so no tests were run. The only change this lane intends to
commit is this report. (The verifications above are `grep`/`sed` reads and one
read-only pass over the merge ledger outside this repo; no test suite applies.)

## What needs a human

1. **The lost-card defect (`lane_merge.raise_decisions` / `lane_produce` /
   `andy_queue`), owner: the lane_merge + decision-queue owner.** 12 cards
   recorded as `raised` with no failure are absent from the queue. Until a filed
   card either leaves a durable trace or the filesystem stops losing it, every
   package parked on a decision stays permanently re-dispatchable, and each pass
   costs a lane. This is not specific to 1043 — 1043 is just the package that
   let me measure it.
2. **1043 itself.** One line of Andy's time: has an incompletely priced client
   upload been seen? Recommend no, keep parked. I have deliberately not queued
   that question, for the reason in the previous section.

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: 1043
-->
