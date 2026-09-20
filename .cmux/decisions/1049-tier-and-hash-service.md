# 1049 — Tier/hash-service design record

**Status:** documented, one decision outstanding
**Owner question:** does `calc_hash_min` have a client?
**Blocks:** any client-facing comparison view built on `bond_static_canonical`

This file is the written-down answer to item 1049's four questions. It does
not replace `SCHEMA.md` §6 or `python/src/static_validator/hashes.py` — those
remain the source of truth for what a tier hashes. The reasoning and the
consumer map live in `docs/coordination.md` §"The calc-hash columns in
`bond_static_canonical`".

---

## The four questions, answered

**1. What fields does each tier hash?**
The tier sets in `hashes.py::_TIER_FIELDS`. `min` = isin, coupon,
maturity_date, frequency, day_count. `std` = min + issue_date,
first_coupon_date. `full` = std + calendar, business_day_convention.
Optional fields are canonical-derivation-populated (SCHEMA.md §4) before
hashing.

**2. Which downstream system reads which tier?**
Client SDK/MCP reads the highest tier both sides hold. The read API
publishes all three. Ops reconciliation and anything doing OAS / spread /
settlement-date work reads `full`. **Nothing reads `min` alone.** — this is
the open decision below.

**3. (1049's implicit third question — is the tiering a security control?)**
No. It is a comparison-granularity feature. Every tier is brute-forceable
because the static is low-entropy, and `min` is the *easiest* to brute-force,
so a higher tier protects nothing the min tier does not already expose. The
brute-force answer is the HMAC tier (WNBF backlog #14), not the tier
structure. Per-field hashes are unsafe as plain SHA-256 (`day_count` has 8
values) and are out of scope until HMAC ships.

**4. Why not per-field hashes now?**
They are the most useful artefact for surgical disagreement reporting and
the most dangerous to publish, for the same reason. Deferred to the HMAC
tier rather than dropped.

---

## The decision

**Does `calc_hash_min` have a client?**

- **Option A — no client; drop the min tier from the published record.**
  Nothing reads it today. Dropping a published artefact nothing consumes is
  additive-compatible and needs no MAJOR bump (SCHEMA.md §7). Fewer tiers,
  less to brute-force, and no "[previously] the min tier" caveat to explain
  to a client.

- **Option B — keep it for sparse-static clients; document the client.**
  A client that holds coupon/maturity/frequency/day_count but not the
  optional dates can still get a meaningful static-drift signal at `min`.
  Costs one more published hash per ISIN and requires the brute-force
  caveat in the README.

**Recommendation: A, but not yet.** Do not drop the column. Dropping it is
a schema decision that should be made against real client data, and we have
no contracted client holding a sparse static. The cheap, reversible move is
to keep populating the column internally with no published consumer until
the first design partner tells us whether they can reach `std`.

**If nobody decides:** the status quo holds — `min` stays populated and
unpublished. That is the default that keeps things moving and forecloses
nothing.

---

## What is NOT in dispute

- The HMAC tier must ship before any public hash database exists (WNBF #14).
- The `sha256:` prefix boundary must be verified before a client is wired to
  these columns — see the reconciliation note in `docs/coordination.md`.
- No hash construction changes as part of this item. This is documentation.
