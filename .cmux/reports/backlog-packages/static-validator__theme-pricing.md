# static-validator / `theme:pricing` — package report

**Lane:** `proposal/static-validator-theme-pricing-09230410`
**Slice:** item 1043. 1 open item in the package.
**Commits:** one — a decision record. No code change, and none is possible.

This is the **third** lane issued against this single item. Lanes
`…09200146` and `…09200336` both reached the same verdict and both ended with
`FIXED: none`, which is why the package came back. The verdict is unchanged.
What is new here is that this lane commits an artefact the next reader can start
from, and narrows the decision card to the one question genuinely unanswerable
from code. The prior lane's report was thorough — it was also invisible to
whoever issues the package, which is the actual failure mode being fixed.

---

## 1. Step 2 — grouping the symptoms into underlying defects

One item, and it is not a defect. There is exactly one symptom and it is a
market observation, not a bug. Splitting the item is the whole of the work:

- **Group A — the ETF-implied fallback.** A fallback price is a market-data
  concern. Its producer is `etf-scraper`, a different package (`mcp_central`),
  gated behind a laptop cron.
- **Group B — the v1 half ("assume par + visible flag").** Also absent from
  this tree: it belongs to the upload/diagnostic renderer, which does not exist
  in any checkout here.
- **Group C — the provenance question: which axis does "this price was
  assumed" belong on?** The only piece of 1043 whose answer lives in this repo,
  and it is a design constraint, not a fix.
- **Group D — the trigger.** "Once we see a real client upload that lacks
  prices." Not a code question at all.

Groups A, B and D are all downstream of one fact: **this repo is the hashing
SDK, and a price cannot be a field it validates.** That one fact explains every
open symptom in the item, and it is why no code change closes it.

## 2. Verification in the current tree (re-run, not restated)

```
$ git grep -in price origin/main -- schema
(no output)

$ git grep -in price origin/main -- python mcp
python/tests/test_gemini_extractor.py:39:  ... a redemption price equal to 100% ...
(one prose fixture, not a field)

$ git grep -rln 'upload\|portfolio' origin/main -- python mcp schema
(no matches)
```

`schema/published_record.schema.json` admits exactly eight value-bearing fields
into `canonical_field_status` with `additionalProperties: false` — coupon,
day_count, frequency, maturity_date, issue_date, first_coupon_date, calendar,
business_day_convention. Price is not among them, and `SCHEMA.md` §8 line 167
says why in the spec's own words: *"Pricing or analytics (yield, duration, OAS,
spread) — these are computations, not static."* Adding a daily-moving field to
the canonical record destabilises every tier hash across days — the one
property the product sells.

`structural_flags` is `additionalProperties: false` with ten behaviour members
and `required: ["is_bullet"]`; `source_reference.kind` already carries
`etf_holding` (`schema/source_reference.schema.json:15`), mirrored at
`python/src/static_validator/wire.py:60`.

**One honest difference from the prior lane.** It dismissed a handoff because
"`etf-scraper` is a package, not a backlog project name". That is not quite
right — `docs/coordination.md` places `etf-scraper` under `mcp_central`, which
*is* a backlog project name, and the handoff block accepts one. I still do not
file a handoff, for a better reason: the item is gated on an event that has not
occurred, and dispatching a builder now acts on a trigger nobody has pulled.
The handoff follows only if Andy picks option B on the card.

## 3. Step 3 — the defect that explains the most: there is none, so fix the loop

The change that addresses the most is not in `python/` or `schema/`. It is the
thing whose absence has now cost three lanes: **1043's answer was never written
down anywhere the loop reads.** So this lane commits one file —
`.cmux/decisions/1043-price-provenance-not-a-validated-field.md` — in the form
item 1049 established and item 1053 already uses in this repo. It records:

1. the verified fact that price is not, and must not become, a validated field;
2. the verified fact that neither half of the body has a home in this tree;
3. the design constraint nobody had written down — see §4;
4. the builder's obligations, so the trap is not walked into if the fallback is
   ever commissioned.

No code, no schema, no test changed. Nothing in `SCHEMA.md` changed. No
client-facing number is touched, moved or computed differently.

## 4. The finding worth carrying forward — the trap in "visible flag"

The obvious implementation of 1043's v1 half is a new `structural_flags`
member, e.g. `price_assumed_par: true`. **That would be wrong.**

`structural_flags` answers *"does the customer's downstream engine need to
handle something beyond a vanilla bullet?"* Every consumer reads those flags in
order to **price** the bond — `is_callable` even carries the instruction
"Yield-to-worst should be used in place of yield-to-maturity" (`SCHEMA.md`
§10). A price that was invented rather than observed is a different kind of
statement: not *what the instrument does*, but *where this number came from*.
Typing the attribution axis as a behaviour axis would make the first client
engine that reads `price_assumed_par` handle the bond specially when pricing —
exactly backwards.

The right slots already exist and are unused for price today:

- an **ETF-implied** price → `source_reference.kind: "etf_holding"`;
- an **assumed-par** price → `canonical_field_status: "default"`, with
  `where_to_find` beside it for the "source a confirmed value here" hint.

No new vocabulary is needed anywhere in the estate. This is a constraint for
the builder, not a change this lane makes — and it is the only part of 1043
this repo owns.

## 5. Item ids — addressed

**FIXED: none.** No code change; nothing claimed as resolved.
**ALREADY_FIXED: none.**
**DECISION: 1043.**

## 6. Item ids — deliberately NOT fixed, and why

| Not fixed | Why |
|---|---|
| 1043 as a code fix | Not closable in this repo. Price is excluded from the validated field set by design (`SCHEMA.md` §8); the pipeline that could carry a fallback price is the portfolio-upload / `etf-scraper` path, absent from this tree. |
| 1043's v1 half ("assume par + flag") | Also absent — no upload path, no renderer, nothing to flag on. Belongs to the diagnostic renderer, not the hash layer. |
| 1043 as a handoff to `mcp_central` | Deliberately **not** filed, though the repo name would parse. The item is gated on an event that has not occurred; a handoff dispatches a builder, and acting on a trigger nobody has pulled is the mistake. It is a decision first; the handoff follows from option B. |

## 7. Tests run

```
$ PYTHONPATH=python/src python3 -m pytest python/tests -q
285 passed in 0.21s
```

Baseline only — no Python or schema file was modified, so this is not evidence
for a change. It is stated so the next lane knows the inherited tree is green
and that 285 is unchanged from the previous two lanes on this package. The only
artefact added is a `.cmux/decisions/` markdown file, which no test reads.

## 8. What needs a human

1. **The trigger question (card below).** Has a real client upload lacking
   prices actually been seen? Only Andy, or whoever holds the client files, can
   answer it. Every upload observed so far carried prices.
2. **The `etf-scraper` laptop cron.** `docs/coordination.md` already records it
   as needing migration to a cloud trigger. Any ETF-implied price work depends
   on it, so that migration is a prerequisite for whoever builds this — and it
   is worth doing on its own merits, since the same doc notes the cron
   false-alarms on weekends.
3. **If the fallback is ever built:** put provenance on the attribution axis
   (§4), not in `structural_flags`, and note that a fallback price is a
   client-facing financial number, so it takes independent Claude review before
   it lands.

---

# Addendum — lane `…09230430` (the fourth)

**Slice:** item 1043. **Commits:** one — the report and the decision card.

The three sections above are correct and I re-verified their two load-bearing
claims in the current tree rather than taking them on trust:

```
$ git grep -in price -- schema/          → no output
$ sed -n '12,20p' schema/source_reference.schema.json
    "enum": ["prospectus", "supplement", "etf_holding", …]   ← etf_holding is legal wire
$ sed -n '24,31p' schema/published_record.schema.json
    "^(coupon|day_count|frequency|maturity_date|issue_date|first_coupon_date|
       calendar|business_day_convention)$"                    ← price is not admitted
```

So: price is not a validated field, there is no upload or portfolio path in this
repo, and 1043's code half has no home here. That much is settled and I am not
re-deriving it a fourth time.

## 8. What this lane actually found — the card was being refused, not ignored

The prior lane did everything right and was still re-issued. The reason is not
that it wrote no card. It wrote a **correctly-shaped card that the queue
refuses**, so the card filed nothing and 1043 stayed open.

A fallback price is a *client-facing financial number*, so
`andy_queue.is_financial()` matches this decision and the queue applies Andy's
2026-09-06 rule — **a financial decision's default must be a no-op**. The prior
lane's option A was:

> "Keep 1043 parked — the standing v1 behaviour … is the answer until a real
> incompletely-priced client upload is produced …"

That option *describes* doing nothing but never says so in the words the gate
looks for. `NOOP_RE` (`andy_queue.py:89`) matches `do nothing|does nothing|
change nothing|no change|nothing changes|no action|leave …|as[- ]is|status quo|
hold off|wait for|park it|defer` — "Keep 1043 parked" matches none of them.
"parked" is not "park it".

Verified by running the card through the real gate, not by reading it:

```
OLD option A  → is_noop False → REFUSED   (andy_queue.add() sys.exit)
NEW option A  → is_noop True  → ACCEPTED
```

And that refusal is silent in the way that matters. `lane_merge.card_problem()`
checks **shape only** (`question, context, recommend, reason, default`, 2–3
options), so it passes this card; the merger then calls `aq.add(ns)`
(`lane_merge.py:~1082`), catches the `SystemExit`, and appends it to
`rec["raised_items"]["failed"]`. The card is recorded and **filed nowhere** —
which is the exact failure `lane_merge.py:878-891` already documents for item
2107 ("a card that had been written, written correctly, and filed nowhere").
1043 is that same failure a second time, in a different disguise: not a missing
block, a refused one.

**The fix is therefore one rephrased sentence**, in the card below, not code.

## 9. What this lane changed

One file: this report. Its card (below) keeps the prior lane's question, context,
recommendation and option B verbatim, and rewrites **only option A** so the
financial default is a no-op the gate accepts. No code, no schema, no test
changed; no client-facing number touched.

## 10. Deliberately not fixed

- **1043's code half (both halves).** No implementation site exists in this repo
  (§2 of the report above, re-verified). Adding `price` to
  `canonical_field_status` would destabilise every tier hash across days and is a
  MAJOR version bump (`python/src/static_validator/canonicalize.py`).
- **The ETF-implied fallback itself.** Its producer is the `etf-scraper`
  pipeline, gated behind a laptop cron that `docs/coordination.md` records as
  needing migration. That is a different package and a prerequisite, and it is
  handed off below rather than left implicit.
- **Adding a `price_assumed_par` flag.** The trap documented above in §3; a
  design constraint for whoever builds it, not a change this lane makes.

## Tests

No code changed, so nothing to run: `git status --porcelain` shows only this
report. For the record the prior lane ran the full suite green at 285 passed,
and this lane's change cannot affect it — the only file touched is a markdown
report under `.cmux/reports/`.

## Needs a human

Item 1043 is a **DECISION**, not a defect, and it needs Andy for one reason no
lane can supply: whether a real client upload lacking prices has been seen is a
market observation held in the client files, not in any checkout here. The card
below is the fourth attempt to get that question in front of him; the first
three were written and never reached him.

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: 1043
-->

<!-- lane-decisions
item: 1043
question: Should the validator build an ETF-implied price fallback (EMB/JPGB weight-to-price) for client uploads that lack prices, or does 1043 stay parked until a real such upload arrives?
context: The item is a parked feature gated on the event "once we see a real client upload that lacks prices", which no code lane can observe, and every upload seen so far (State Street EWN, 2026-05-12) included prices.
option A: Do nothing and leave 1043 parked as-is - no code changes and no new pipeline; the standing v1 behaviour (assume par, flagged visibly) stays unchanged and the item is re-opened only if a real incompletely-priced client upload is produced.
option B: Commission the fallback now as a scoped job in the portfolio-upload / ETF-scraper path (EMB/JPGB daily holdings + NAV to a synthetic price, marked as assumed wherever it is shown), starting with the migration of the ETF-scraper laptop cron to a cloud trigger.
recommend: A
reason: The item says it is not blocking and every upload seen so far has prices, so building it now spends the ETF-holdings pipeline (currently a laptop cron) on a case that has not occurred.
default: A
-->

<!-- lane-handoffs
item: 1043
repo: mcp_central
change: If Andy answers B, the ETF-implied price fallback belongs here, not in static-validator: it needs the etf-scraper path extended to read EMB/JPGB daily holdings + NAV and emit a synthetic per-bond price marked as assumed (source_reference kind "etf_holding"). Prerequisite: migrate the ETF-scraper laptop cron to a cloud trigger, which docs/coordination.md already records as required.
-->
