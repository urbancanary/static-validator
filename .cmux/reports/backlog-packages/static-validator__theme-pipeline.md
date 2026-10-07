# static-validator — package `theme:pipeline` (lane slice: item 5669)

**Lane:** `lane/auto-static-validator-theme-pipeline-10071424` (8th lane on this package)
**Item:** 5669 — "validate-portfolio quantlib_calc v0.2: build AmortizingFixedRateBond from
bond_cashflow_schedule" — file named: `validate_portfolio/quantlib_calc.py`

## Verdict: HANDOFF — the fix is already built, in `google-analysis11`

Three previous lanes answered this item **DECISION** ("which repo owns `validate_portfolio`?",
`d26fdbd`, merged `20b69c7`). That question is now answerable from the tree, and the answer is
that **the defect described in the item is already fixed in the repository that owns this code**.
Nothing in static-validator can close it, and nothing should be built here.

### The file the item names does not exist — confirmed in this tree (not inherited)

```
$ git log --oneline --all -- validate_portfolio/quantlib_calc.py
(no output; the path appears in no commit in this repo, on any branch)
$ find . -name 'quantlib_calc*' -o -name 'validate_portfolio*'
(no output)
```
The only Python package here is `python/src/static_validator/`. `README.md:93` advertises
`validate-portfolio` as "v0.2 (current)" — the item was filed from that roadmap line, not from
code. `docs/coordination.md:20,81,217` places QuantLib in the estate in exactly two consumers:
`ga10-pricing-mcp` (CBonds + QuantLib pricing) and, by the code itself, the google-analysis
repos. No `quantlib_calc.py` exists on this host (searched `/opt/work/*`, depth 4).

### Ownership, from the code rather than a guess

`grep -n "is_amortizing" /opt/work/google-analysis11/v3_slim/calc/quantlib_engine.py` — the
`BondPack` docstring at **line 283** reads

```
bond: Any                       # ql.FixedRateBond OR ql.AmortizingFixedRateBond
```

and **line 532** `if is_amortizing:` builds exactly what the item asks for, from the
`bond_cashflow_schedule` rows (`sinking_cashflows`) — **line 567**:

```
bond = ql.AmortizingFixedRateBond(
    0, notionals, amort_schedule, [coupon_decimal], day_counter,
    payment_convention,
)
```

### The item is satisfied, and by more than the item asks for

The item's desired behaviour is "for `is_amortizing` bonds a `ql.AmortizingFixedRateBond` with
per-period notionals is used and **accrued differs from bullet as expected**". Both halves hold:

1. **Per-period notionals** — `quantlib_engine.py:532-567`, notionals =
   `pool_factor * 100` per period, final maturity notional excluded.
2. **Accrued** — `quantlib_engine.py:749-753` returns `pack.bond.accruedAmount(settle_ql)` on
   the bond actually built, with the comment "For amortizers, use the bullet schedule view for
   accrued (matches what `QL.accruedAmount` returns on `AmortizingFixedRateBond` per period)".
   The v0.1 bug the item describes — accrued on a bullet bond for an amortizer — is gone: on an
   amortizer the object returned is the amortizing bond, not the bullet.
3. **Guard** — `quantlib_engine.py:386-390` raises `ValueError` when `is_amortizing=True` and no
   sinking schedule was supplied, instead of silently pricing a bullet — which is precisely the
   failure mode v0.1 had.

Upstream of it, `google-analysis11` also carries a newer, dedicated implementation,
`amortizing_bond_calculator.py:227` and `:314`, and an integration test,
`google-analysis11/test_amortizing_integration.py`.

**I changed nothing.** The work named by item 5669 is done in `google-analysis11`; a lane sent
there will find it done too, and should say so rather than edit.

---

## Why this lane does not re-file the same DECISION

`d26fdbd` (5669) and `981b980`/`84ab3fb` (5667, 5668) each filed a card asking "which repository
owns `validate_portfolio`?". The question is answered above from `quantlib_engine.py:283,532,567`.
Filing it a fourth time would put the same question in front of Andy again and leave 5669 open for
a ninth lane, which is the loop this lane exists to break.

## Tests run

None. No file in this repository was changed, so there is no test here to run. The evidence is
`file:line` in the owning repository, not a diff in this one (`grep` output quoted above).

## What remains open (owned by the next lane on this package)

- 5669 — handled here as a handoff; the fix exists in `google-analysis11` (evidence above).
- The other 3 open items of package `theme:pipeline` are outside my slice and were not touched.
- If the intent is that the skill be *relocated* into `static-validator` rather than stay in the
  analysis repos, that is an architecture decision for Andy, not a code fix, and it is not
  covered by item 5669 — that item asks only that amortizers be built with
  `ql.AmortizingFixedRateBond`, which they already are.

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: none
-->

<!-- lane-handoffs
item: 5669
repo: google-analysis11
change: Verify (do not rebuild) that the amortizing path is correct and covered: `v3_slim/calc/quantlib_engine.py:532-567` already builds `ql.AmortizingFixedRateBond` with per-period notionals from `bond_cashflow_schedule` sinking rows, and `:749-753` takes accrued from the built bond, so the item's stated defect (bullet accrued on an amortizer) is already gone. `amortizing_bond_calculator.py:227,314` and `test_amortizing_integration.py` carry the dedicated implementation and test.
-->
