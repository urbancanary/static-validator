# static-validator — item 5669

**Lane:** `proposal/mini-5669-1006232556`
**Item:** 5669 — *validate-portfolio quantlib_calc v0.2: build AmortizingFixedRateBond from bond_cashflow_schedule*
**Reviewer-supplied path:** `validate_portfolio/quantlib_calc.py`

## Verdict: DECISION

There is no `validate_portfolio/` package, no `quantlib_calc.py`, and no QuantLib
code of any kind in this repository — and there cannot be one at the named path,
because the directory that holds the `validate-portfolio` skill is excluded by
`.gitignore`. A lane cannot make this change here and cannot commit it here. A
person has to say where the skill is versioned before the item can be worked.

## What the item asks

> v0.1 treats every bond as a bullet FixedRateBond even when `canonical.is_amortizing`
> is True, so accrued is wrong for amortizers. Wanted: for `is_amortizing` bonds a
> `ql.AmortizingFixedRateBond` with per-period notionals is used and accrued differs
> from bullet as expected.

The premise is that a v0.1 `quantlib_calc` exists with a bullet `ql.FixedRateBond`
constructor and needs a branch added. Nothing of the sort is in this tree.

## Verified in this clone, not inherited from the item

```
$ ls validate_portfolio
ls: validate_portfolio: No such file or directory

$ grep -rn "AmortizingFixedRateBond" . | grep -v .git/ | wc -l
0
$ grep -rn "FixedRateBond" . | grep -v .git/ | wc -l
0
$ grep -rln "quantlib_calc\|validate_portfolio" .
(nothing)

$ git ls-files | grep -i "quantlib\|validate_portfolio" | wc -l
0
$ git log --all --oneline -- "*quantlib_calc*" "*validate_portfolio*"
(nothing, on any branch, ever)
```

`python/pyproject.toml` has `dependencies = []`; `mcp/pyproject.toml` pulls only
`static-validator` and `mcp`. No QuantLib, no pricing module, no consumer of
`bond_cashflow_schedule` anywhere in `python/src`, `mcp/src`, or the tests. This
repo is the canonical-static SDK: schema, canonical JSON, tier hashes, structural
flags. Pricing is not a code path it has.

## Why the named path cannot hold the change

The v0.2 skill is advertised in the repo's own README, and it is the only place in
the tree that mentions the QuantLib analytics the item describes:

> `README.md:98`: `.claude/skills/validate-portfolio/` — orchestration skill for the
> diagnostic pipeline; same code serves all three tiers via config flags

But `.gitignore` ends with:

```
$ tail -1 .gitignore
.claude/
```

So the entire skill directory — the only home the repo names for
`validate-portfolio` — is untracked by design. It is absent from this clone, no
branch in `git log --all` has ever carried it, and any edit placed under it would
be discarded rather than committed. The reviewer's path (`validate_portfolio/…`,
no `.claude/skills/` prefix) matches neither the README location nor any file on
this host: a recursive search of `/Users/andrewseaman` for `quantlib_calc.py`,
`validate_portfolio/`, or `validate-portfolio/` returns nothing.

## The change would also move a client-facing financial number

Even if the file were present, the item's wanted result is a change to **accrued
interest** — expressly one of the client-facing financial figures the lane brief
says must stop for independent review. A bullet-vs-amortizing branch in a bond
constructor alters accrued and, downstream, dirty price. This is not a change a
lane should land against a spec it cannot see; it needs the skill's owner and a
reviewer.

## The decision

**Where does the v0.2 `validate-portfolio` skill live, and should it be brought
under version control, before any `quantlib_calc` amortizing work is dispatched?**

- **Option A** — Un-ignore the skill (drop `.claude/` from `.gitignore`, or move
  the skill to a tracked path such as `python/validate_portfolio/`), land the v0.1
  skill as-is, then re-file the amortizing item against a real path with a real
  review target.
- **Option B** — Keep the skill local-only and out of this repo. Then item 5669 is
  not a `static-validator` item at all; re-file it against whatever repo owns the
  skill, and stop routing it to this project.

Recommend **A**: the README already presents the skill as part of the repo layout
while `.gitignore` silently contradicts it, so a client-facing calc is being built
in a directory no reviewer, no CI job, and no lane clone can see. One line of
`.gitignore` is what makes item 5669 unworkable here.

No code changed. No key, token or password appears in this report.

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: 5669
-->
