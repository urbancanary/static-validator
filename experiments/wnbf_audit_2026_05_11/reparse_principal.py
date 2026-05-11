"""
Second-pass reparse: fix principal_repayment misclassifications.

The original parser caught the template echo ("Single bullet or installments:")
and mislabeled bonds as AMORTIZING. This pass reads the actual answer text
inside B1 and applies an evidence-ordering rule:
  - if 'bullet at maturity' present and no 'scheduled installments' → BULLET
  - elif 'scheduled installments' or 'amortiz' (the answer-words) → AMORTIZING
  - elif 'bullet' → BULLET
  - else UNKNOWN

Only updates rows where locked = FALSE.
"""
import json
import re
import urllib.request

SUP = "https://xdgicslrdudsqlsudsgv.supabase.co/rest/v1"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhkZ2ljc2xyZHVkc3Fsc3Vkc2d2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MzU0Nzk1MywiZXhwIjoyMDg5MTIzOTUzfQ.clGHMQCcuBoQ7ncDdqKVNlCPlJN3zjvaUyhQ0eD2cmw"
RUN_ID = "wnbf_2026_05_11_v2"

HEADERS_READ = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
HEADERS_WRITE = {**HEADERS_READ, "Content-Type": "application/json", "Prefer": "return=minimal"}


def parse_principal(raw_text):
    """Return BULLET | AMORTIZING | UNKNOWN. Use the FIRST-SENTENCE rule."""
    if not raw_text:
        return "UNKNOWN"
    m = re.search(r"\*?\*?\s*B1[.\):*\s]+([\s\S]*?)(?=\n\s*\*?\*?\s*B2[.\):*\s]|\n\s*\*?\*?\s*B3[.\):*\s]|\Z)", raw_text)
    if not m:
        return "UNKNOWN"
    b1 = m.group(1).lower()
    # Strip template-echo phrases like "single bullet or installments:**" so we see the actual answer
    answer = re.sub(r"single bullet or installments?[:\s\*]+", "", b1)
    # Take just the first sentence (up to first period that ends a clause).
    # This avoids parenthetical remarks like "(no scheduled amortization)" from contaminating the signal.
    first_sentence = re.split(r"\.(?:\s|$)", answer.strip(), maxsplit=1)[0]
    # Decide based on first-sentence content
    if "scheduled installment" in first_sentence or "amortiz" in first_sentence:
        return "AMORTIZING"
    if "bullet" in first_sentence:
        return "BULLET"
    # Fallback to full-B1 with negation-awareness
    # Remove negated phrases like "no scheduled amortization" / "not subject to a sinking fund"
    cleaned = re.sub(r"\bno\s+(?:scheduled\s+)?(?:amortiz\w+|installments?|sinking)\b", "", answer)
    cleaned = re.sub(r"\bnot\s+(?:subject\s+to|amortiz\w+|an?\s+installment)\b", "", cleaned)
    if "scheduled installment" in cleaned or "amortiz" in cleaned:
        return "AMORTIZING"
    if "bullet" in cleaned:
        return "BULLET"
    return "UNKNOWN"


# Fetch unlocked rows
url = f"{SUP}/bond_static_audit_findings?run_id=eq.{RUN_ID}&locked=eq.false&select=id,isin,principal_repayment,raw_text,amortization_schedule"
with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS_READ), timeout=30) as r:
    rows = json.loads(r.read())

print(f"Re-parsing principal_repayment for {len(rows)} unlocked rows…\n")
changed = []
for r in rows:
    old = r.get("principal_repayment")
    new = parse_principal(r.get("raw_text"))
    if old != new:
        changed.append((r["isin"], old, new, r["id"]))
        print(f"  {r['isin']}  {old}  →  {new}")

print(f"\n{len(changed)} rows need principal_repayment correction.")

# Apply updates, scoped to locked=FALSE
for isin, old, new, rid in changed:
    body = {"principal_repayment": new}
    # If we're flipping FROM AMORTIZING TO BULLET, also null out amortization_schedule
    if old == "AMORTIZING" and new == "BULLET":
        body["amortization_schedule"] = None
    url = f"{SUP}/bond_static_audit_findings?id=eq.{rid}&locked=eq.false"
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                  headers=HEADERS_WRITE, method="PATCH")
    with urllib.request.urlopen(req, timeout=30) as r:
        print(f"  UPDATED {isin}  -> principal={new}{' (schedule cleared)' if 'amortization_schedule' in body else ''}")

# Verify final state
print("\nFinal AMORTIZING set (after both reparses):")
url = f"{SUP}/bond_static_audit_findings?run_id=eq.{RUN_ID}&principal_repayment=eq.AMORTIZING&select=isin,vendor_ticker,trust_class,amortization_schedule&order=isin"
with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS_READ), timeout=30) as r:
    for x in json.loads(r.read()):
        sched = x.get("amortization_schedule") or []
        n = len(sched) if isinstance(sched, list) else 0
        marker = "✓" if n >= 2 else "partial" if n == 0 else "?"
        print(f"  {x['isin']:14s} {x['vendor_ticker']:12s}  trust={x['trust_class'][:30]:30s}  n_installments={n}  ({marker})")
