# static-validator — item 5667

**Lane:** `proposal/mini-5667-1006232520`
**Item:** 5667 — "validate-portfolio: write cli.py and config.py for python -m validate_portfolio"
**Reviewer's pointer:** `validate_portfolio/cli.py`
**Result: the item's premise does not hold against this repo. Nothing to build here.**

---

## 1. The item, verbatim, and what it assumes

> Six of eight stages exist, each with its own `__main__`; no unified entry point. `config.py`
> must resolve `TRUST_MODE` / `ENRICHMENT_SOURCE` / `PERSISTENCE` / `RENDER_TARGET` defaults
> per the `SKILL.md` table.
>
> Wanted result: `python -m validate_portfolio` runs the pipeline end to end on
> `samples/state_street_ewn_20260430.tsv` in Tier 0/1 mode with flags honoured.

That assumes a repository containing all of:

1. a package `validate_portfolio/` with a `cli.py` and a `config.py`;
2. an eight-stage pipeline, six stages already present, each with its own `__main__`;
3. a `SKILL.md` carrying a defaults table for `TRUST_MODE` / `ENRICHMENT_SOURCE` /
   `PERSISTENCE` / `RENDER_TARGET`;
4. `samples/state_street_ewn_20260430.tsv` — a real State Street OMS export to run against.

## 2. Verified against the tree, not inherited

```
$ find . -path ./.git -prune -o -name validate_portfolio -print -o -name config.py -print \
      -o -name SKILL.md -print -o -name '*.tsv' -print
(no output)

$ grep -rn "TRUST_MODE|ENRICHMENT_SOURCE|RENDER_TARGET|validate_portfolio|PERSISTENCE" . --exclude-dir=.git
(no output)

$ git ls-files          # the whole tracked tree, 60 files
```

| The item assumes | In this repo |
|---|---|
| `validate_portfolio/` package | absent — the only Python package is `python/src/static_validator/` |
| `validate_portfolio/cli.py` | absent; the CLI is `python/src/static_validator/cli.py` |
| `config.py` with the four settings | absent — no `config.py` anywhere, and no occurrence of those four names in any tracked file |
| eight stages, six with own `__main__` | absent — `static_validator` has eight *modules* (`adapter`, `canonicalize`, `cli`, `derivations`, `gemini_extractor`, `hashes`, `validate`, `wire`) and exactly one `__main__.py`, which just calls `cli.main` |
| `SKILL.md` defaults table | absent — no `SKILL.md` in the repo |
| `samples/state_street_ewn_20260430.tsv` | absent — no `samples/` directory and no `.tsv` file |

The entry point that does exist is a different thing entirely:

```
python/src/static_validator/cli.py:28   prog="static_validator"
python/src/static_validator/cli.py:31   sub.add_parser("hash", ...)
python/src/static_validator/cli.py:35   sub.add_parser("canonical", ...)
```

`python -m static_validator` hashes a single bond JSON record or emits its canonical form at a
tier (`cli.py:1-7`). It is a per-record tool with two subcommands — not a portfolio pipeline,
not eight stages, and not driven by a trust/enrichment/persistence/render config.

`git log --oneline -5 -- validate_portfolio/cli.py` and `git log --oneline --grep 5667` both
return nothing: no commit ever added the named file, and no prior lane addressed this item.

## 3. Why this is a decision, not a fix

A FIX would be "one small, clear change you can finish and test inside your budget". There is
no such change. To satisfy the item I would have to invent, from nothing: the eight-stage
pipeline, the `SKILL.md` defaults semantics, and a State Street sample file — then claim the
pipeline "runs end to end". That is authoring a new program and its test fixture, not closing a
backlog defect, and every one of those inventions is a guess about a design no artifact in this
repo records.

The honest reading is that **item 5667 was filed against a different artifact than this
checkout**. This repository is `static-validator`: a canonical-schema library, an MCP stdio
server, and an experiments workspace. It does not contain a `validate_portfolio` pipeline, and
nothing here has the six existing stages the item says are already done. (`docs/coordination.md`
names four sibling repos — `rvm_app_v2`, `etf-scraper`, `ga10-pricing-mcp`, `static-validator` —
but none of them is `validate_portfolio`.)

A person has to resolve one thing before any code can be written:

> **Which repository or project owns `validate_portfolio` — and where are its existing six
> stages, its `SKILL.md` defaults table, and the `samples/state_street_ewn_20260430.tsv` fixture?**
> If it is this repo, the pipeline must be specified first; it is not present and cannot be
> reconstructed from anything here.

## 4. What I did not do

I did not create `validate_portfolio/`, `config.py`, a `SKILL.md`, or a fabricated sample TSV.
Doing so would make the item look closed while shipping a pipeline invented to match the
wording of the item, with no design source and no real data behind it. No existing file was
modified; the tree is unchanged apart from this report.

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: 5667
-->
