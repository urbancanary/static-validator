# static-validator — theme:pipeline

**Item:** 5670 — validate-portfolio live full-sample run and edge cases
**Verdict:** DECISION. The requested `validate_portfolio/classifier.py` and
`state_street_ewn_20260430.tsv` are absent from this checkout. `rg --files` finds
neither; searches for `GREENSAIF`, `first_coupon_end`, and country alias/classifier
symbols find no relevant implementation. The existing Python package is
`python/src/static_validator/`, a different tool. There is no honest code fix or
run result available here.

No code tests were run because no implementation file is present to change.
Nothing was fixed. Andy needs to identify the repository that owns
`validate_portfolio` and provide/locate the sample and existing classifier before
a live run can be performed.

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: 5670
-->

<!-- lane-decisions
item: 5670
question: Which repository owns validate_portfolio and its State Street sample?
context: This checkout has no validate_portfolio classifier or named TSV, so the requested live run cannot be performed here.
option A: Identify the repository containing the existing pipeline and sample, then route the item there.
option B: Treat validate_portfolio as a new project and provide its design and source data before implementation.
recommend: A
reason: The item describes an existing pipeline, so locating that artifact is the smallest step that enables its requested run.
default: A
-->
