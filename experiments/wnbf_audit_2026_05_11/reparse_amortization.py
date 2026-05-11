"""
Reparse amortization_schedule from raw_text, scoped to the B2 (installments)
section only. Push the corrected values back to Supabase, but ONLY for rows
where locked = FALSE.
"""
import json
import re
import urllib.request

SUP = "https://xdgicslrdudsqlsudsgv.supabase.co/rest/v1"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhkZ2ljc2xyZHVkc3Fsc3Vkc2d2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MzU0Nzk1MywiZXhwIjoyMDg5MTIzOTUzfQ.clGHMQCcuBoQ7ncDdqKVNlCPlJN3zjvaUyhQ0eD2cmw"
RUN_ID = "wnbf_2026_05_11_v2"

HEADERS_READ = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
HEADERS_WRITE = {**HEADERS_READ, "Content-Type": "application/json", "Prefer": "return=minimal"}


def fetch_unlocked():
    url = f"{SUP}/bond_static_audit_findings?run_id=eq.{RUN_ID}&locked=eq.false&select=id,isin,principal_repayment,raw_text,amortization_schedule"
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS_READ), timeout=30) as r:
        return json.loads(r.read())


def parse_amort_schedule(raw_text, principal):
    """Return parsed schedule list, or None if not AMORTIZING."""
    if principal != "AMORTIZING" or not raw_text:
        return None
    # Find the B2 block: starts at 'B2' marker, ends at 'B3' marker (or 'C.' if B3 missing)
    m = re.search(r"B2[.\):\s\*]+([\s\S]*?)(?=\n\s*(?:\*?\*?)\s*B3[.\):\s]|C\s*\.\s*CALL|\Z)", raw_text, re.IGNORECASE)
    if not m:
        return None
    b2_block = m.group(1)
    # Look for date-percentage pairs.
    # Date formats: "July 23, 2058" / "23 July 2058" / "2058-07-23" / "May 15 of each year, commencing on May 15, 2058"
    # Percentage formats: "(33.33%)" / "33.33%" / "33.33 %"
    pairs = []
    # Try pattern: "<Month Day, Year>... (XX.XX%)" or "<date>: XX.XX%"
    for m in re.finditer(
        r"(?P<date>(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})"
        r"[\s\(\)\:\-]{1,30}"
        r"(?P<pct>\d{1,3}(?:\.\d{1,4})?)\s*%",
        b2_block,
    ):
        try:
            pct = float(m.group("pct"))
        except ValueError:
            continue
        pairs.append({"date": m.group("date").strip(), "pct": pct})
    # If we found nothing with that strict pattern, return None (will leave as is)
    if not pairs:
        return None
    # Sort by date if possible (best-effort)
    # Dedupe by (date, pct)
    seen = set()
    deduped = []
    for p in pairs:
        k = (p["date"], p["pct"])
        if k not in seen:
            seen.add(k)
            deduped.append(p)
    return deduped


def update_amort(row_id, schedule):
    body = {"amortization_schedule": schedule}
    url = f"{SUP}/bond_static_audit_findings?id=eq.{row_id}&locked=eq.false"
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                  headers=HEADERS_WRITE, method="PATCH")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


rows = fetch_unlocked()
print(f"Reparsing amortization_schedule for {len(rows)} unlocked rows…")
print()
updated = nochange = cleared = 0
for r in rows:
    new_sched = parse_amort_schedule(r.get("raw_text"), r.get("principal_repayment"))
    old_sched = r.get("amortization_schedule")
    # Three cases: AMORTIZING with new schedule, non-AMORTIZING (should be null), or no change
    if r.get("principal_repayment") != "AMORTIZING":
        # null out any noise on bullet bonds
        if old_sched is not None:
            update_amort(r["id"], None)
            print(f"  CLEARED  {r['isin']}  (was {len(old_sched)} noise entries, now NULL)")
            cleared += 1
        else:
            nochange += 1
    else:
        if new_sched is None:
            # parser couldn't find — leave as is, flag
            print(f"  SKIPPED  {r['isin']}  AMORTIZING but B2 parser found nothing (manual review)")
            nochange += 1
        elif new_sched != old_sched:
            update_amort(r["id"], new_sched)
            print(f"  UPDATED  {r['isin']}  -> {len(new_sched)} installments: {new_sched}")
            updated += 1
        else:
            nochange += 1

print()
print(f"Summary: updated={updated}  cleared={cleared}  no_change={nochange}")

# Verify
url = f"{SUP}/bond_static_audit_findings?run_id=eq.{RUN_ID}&select=isin,principal_repayment,amortization_schedule&order=isin"
with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS_READ), timeout=30) as r:
    all_rows = json.loads(r.read())
print()
print("Final state for AMORTIZING bonds:")
for x in all_rows:
    if x.get("principal_repayment") == "AMORTIZING":
        sched = x.get("amortization_schedule")
        n = len(sched) if isinstance(sched, list) else 0
        print(f"  {x['isin']}  n_installments={n}  schedule={sched}")
