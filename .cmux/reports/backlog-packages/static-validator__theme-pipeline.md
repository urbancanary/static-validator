# static-validator — package `theme:pipeline` (lane slice: item 5669)

**Lane:** `lane/auto-static-validator-theme-pipeline-10071406`
**Package:** theme:pipeline — 4 open items, my slice is 1.
**Item:** 5669 — "validate-portfolio quantlib_calc v0.2: build AmortizingFixedRateBond from
bond_cashflow_schedule"
**File named by the item:** `validate_portfolio/quantlib_calc.py`
**Verdict: DECISION — the file, the function and the repository the item assumes are all absent
from this checkout. No code can close it here.**

---

## 1. What the item says, and what it assumes exists

> v0.1 treats every bond as a bullet FixedRateBond even when canonical.is_amortizing is True, so
> accrued is wrong for amortizers.
>
> Desired behaviour: For is_amortizing bonds a `ql.AmortizingFixedRateBond` with per-period
> notionals is used and accrued differs from bullet as expected.
>
> File: `validate_portfolio/quantlib_calc.py`

That assumes, in this repository:

1. a package directory `validate_portfolio/` with a module `quantlib_calc.py` in it;
2. a v0.1 of that module that builds `ql.FixedRateBond` unconditionally;
3. a `bond_cashflow_schedule` (the item's title) to build per-period notionals from;
4. QuantLib as an importable dependency of this repo.

## 2. Verified against the tree, not inherited

```
$ git log --oneline -5 -- validate_portfolio/quantlib_calc.py
(no output — no commit in this repo has ever touched that path)

$ find . -path ./.git -prune -o \( -name 'quantlib_calc*' -o -name 'validate_portfolio*' \) -print
(no output)

$ grep -rn "quantlib\|QuantLib" . --exclude-dir=.git
(no output — the word QuantLib appears nowhere in any tracked file, not in code,
 not in a dependency list, not in a test)
```

| The item assumes | In this repo |
|---|---|
| `validate_portfolio/` package | **absent.** The only Python package is `python/src/static_validator/` (`adapter.py`, `canonicalize.py`, `cli.py`, `derivations.py`, `gemini_extractor.py`, `hashes.py`, `validate.py`, `wire.py`) |
| `validate_portfolio/quantlib_calc.py` | **absent** — no `quantlib_calc.py` anywhere; the substring `quantlib` occurs in no tracked file |
| a v0.1 bullet `FixedRateBond` builder to amend | **absent** — nothing to amend |
| `bond_cashflow_schedule` | **absent** — no such field, function or schema node |
| QuantLib dependency | **absent** — not imported, not declared, never named |

The upstream this item is a child of is item **1057, "validate-portfolio skill: complete cli.py +
config.py + persistence.py"** — the same phantom package. It was already worked and reported on:
`.cmux/reports/backlog-packages/static-validator__5667.md` (commit `981b980`, merged as `3ea9e6d`,
"Report: static-validator / 5667 — validate_portfolio does not exist in this repo") reaches the
same finding for the sibling item and cites the same evidence: no `validate_portfolio/`, no
`SKILL.md`, no `samples/`, no `config.py`.

`README.md:93` explains where the phrase comes from — "**v0.2 (current)** — `validate-portfolio`
skill: OMS-export parser (starting with State Street), QuantLib analytics, convention inference,
Athena-style diagnostic HTML". That is a **roadmap line describing an unbuilt skill**, not a
description of code in this repo. The backlog items in this package were filed by reading the
roadmap as though it described the tree.

## 3. What the repo *does* have on this theme, and why it is not the item

This repo does model amortization, in three places, all reported not priced:

- `schema/structural_flags.schema.json:11` — `"is_amortizing": {"type": "boolean",
  "description": "Principal amortizes evenly across coupon dates."}` — a published structural flag.
- `python/src/static_validator/wire.py:45` — `is_amortizing: bool` on the wire record.
- `python/src/static_validator/validate.py:49` — the flag raises the warning *"bond is amortizing
  — principal repays before maturity; bullet-mode pricing will be wrong"*.

That last line is the repo's current answer to exactly the defect item 5669 describes: it
**detects** the bullet-mode mispricing and **says so in the diagnostic**, without computing a
price. `README.md:34` is explicit that this is the product design, not a gap — the customer's
reported yield matching our bullet model *is the finding*: "The customer's reported yield matches
our bullet model exactly — so we know their system is pricing them as bullets — but the bonds are
amortizers, and their numbers are wrong." Building an `AmortizingFixedRateBond` to re-price
amortizers is the v0.2 pipeline's job, and that pipeline does not exist in this repo.

I deliberately did not build it here. The named file is not here, `bond_cashflow_schedule` has no
definition anywhere, and every decision in the item — where the schedule comes from, how per-period
notionals are derived for an *evenly*-amortizing flag, whether the schema can even express them —
would be invented by me to match the wording of the item. That is authoring a module and shipping
an amortization formula that nothing in this repo specifies.

## 4. What is not being changed

No file was modified. In particular I did **not**:

- create `validate_portfolio/` or `quantlib_calc.py`;
- add QuantLib as a dependency;
- touch `validate.py:49`, `wire.py:45` or `schema/structural_flags.schema.json:11` — the flag,
  the warning and the schema are correct as they stand and are not the item;
- change any financial number. (None could be moved: this item touches accrued, which is a
  client-facing figure — had the module existed and had I built the amortizer, that would have
  been a STOP-and-hand-back under the standing rule, since a first amortizing accrual
  implementation is exactly the kind of change that needs independent review by a Claude session.)

## 5. Tests

None run. No file was changed, so there is no file to run tests for.

## 6. What needs a human

One question, and it is the same one item 5667 already raised — I am not re-asking it as a second
card, and `covers:` names 5669 so the two are settled together:

> **Does `validate_portfolio` exist as a project at all — and if so, in which repository?**
> The v0.2 skill behind items 1057 / 5667 / 5669 (CLI, config, persistence, QuantLib analytics,
> `bond_cashflow_schedule`, State Street sample) is described in `README.md:93` as "current" but no
> artifact of it is present in `static-validator`, and no sibling repo named in
> `docs/coordination.md` owns it. Until that is answered, every item in this package is
> unactionable by a lane and will keep coming back.

If the answer is "it is this repo", the pipeline must be **specified** before it is coded: the
package, the module layout, the `bond_cashflow_schedule` structure, and where per-period notionals
come from. That specification is a decision, not a fix.

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: 5669
-->

<!-- lane-decisions
item: 5669
covers: 1057, 5667
question: Does `validate_portfolio` exist as a project, and if so in which repository — or should every validate-portfolio backlog item (1057, 5667, 5669 and the rest of the theme) be closed as filed against an artifact that was never built?
context: Item 5669 names `validate_portfolio/quantlib_calc.py`, which is not in static-validator; no tracked file in this repo contains the string "quantlib", and README.md:93 describes the validate-portfolio skill as "v0.2 (current)" while no code for it exists anywhere a lane can reach.
option A: Declare validate-portfolio a separate, not-yet-built project — close 1057/5667/5669 and their package siblings as "artifact does not exist", to be re-filed against the real repo once one is created.
option B: Keep validate-portfolio in static-validator — task a Claude session to write the pipeline specification first (package layout, bond_cashflow_schedule, where per-period notionals come from) before any lane is sent at the code items again.
recommend: A
reason: Four lanes have now been sent at this package and found no code to change, so leaving the items open only re-issues the same reading; if the pipeline is meant to live here, option B's specification is the next artifact and should be an explicit task rather than an inferred one.
default: A
-->

<!-- lane-handoffs
item: 5669
repo: athena_html_v3
change: If the validate-portfolio v0.2 pipeline (QuantLib analytics, amortizing-bond accrued) is in fact served from athena_html_v3 rather than static-validator, this item's fix belongs there, in whatever module builds the QuantLib bond object for a cashflow schedule — but no such module or route was verifiable from this clone, so confirm ownership before sending a lane.
-->
