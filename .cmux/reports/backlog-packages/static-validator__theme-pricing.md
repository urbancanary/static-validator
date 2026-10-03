# static-validator / `theme:pricing` — package report

**Lane:** `proposal/static-validator-theme-pricing-10030654`
**Slice:** item 1043 (the only open item in this package).

This lane confirmed `python/src/static_validator/wire.py:60` still lists `etf_holding` as a source-reference kind. That line describes provenance metadata; it does not add a price field or an ETF fallback. The item remains gated on a real incomplete-price client upload, so this lane makes no code change and repeats the decision card because the item remains open.

## Grouping and disposition

1043 is one gated feature request, with two implementation ideas: assume par
with a visible flag for the current v1 behavior, and later derive a synthetic
price from ETF holdings and NAV. These are not defects in `static-validator`.
The supplied disposition records the recommendation to keep the feature parked
until a real client upload without prices appears.

The repository is the static validation SDK/schema. The current
`schema/published_record.schema.json` admits only coupon, day count, frequency,
dates, calendar, and business-day convention in `canonical_field_status`, with
`additionalProperties: false`; price is excluded. Adding a moving market value
there would change the static validation/hash contract. The upload parser and
diagnostic renderer described by the item are not in this repository. The ETF pipeline is separately
owned and its recorded laptop-cron migration remains a prerequisite. No code or
client-facing financial number is changed here.

## Item accounting

- **1043 — DECISION.** Whether the real-upload trigger has occurred, and whether
  to commission ETF fallback work before it does, cannot be answered from this
  repository. The recommendation is to keep it parked; the card below puts that
  choice in the estate decision queue. If Andy chooses to build it, the work
  belongs in the portfolio-upload / `etf-scraper` path after its cron migration.

No items were fixed or already fixed. No handoff is filed while the feature is
parked: the downstream build is conditional on the human decision, and queuing
it now would dispatch work before the trigger/commissioning question is settled.
The existing decision record at
`.cmux/decisions/1043-price-provenance-not-a-validated-field.md` also records
that the consumer and renderer are absent here. If commissioned, the work must
be routed to the owning portfolio/ETF pipeline.

## Tests

No code changed, so no tests were run. This report is the only intended file
change.

## Human decision

The recommended outcome is to leave the feature parked pending a real
incompletely priced client upload. The alternative commissions the separate
ETF pipeline now. Option A is explicitly a no-op because the choice concerns a
client-facing price.

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: 1043
-->

<!-- lane-decisions
item: 1043
question: Should the ETF-implied price fallback remain parked until a real client upload without prices appears, or should the work be commissioned now?
context: The item is explicitly gated on a missing-price client upload, while the only observed example in its record included prices.
option A: Do nothing and keep 1043 parked; retain the stated v1 behavior until a real incompletely-priced client upload appears.
option B: Commission the fallback now in the portfolio-upload and ETF-scraper path, beginning with migration of the ETF-scraper laptop cron.
recommend: A
reason: The recorded examples include prices and the item says the feature is not blocking, so building it now would spend effort on an unobserved case.
default: A
-->
