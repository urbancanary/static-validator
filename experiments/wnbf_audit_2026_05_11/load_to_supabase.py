"""
Load WNBF audit findings via Supabase REST (PostgREST).
Run row already inserted via MCP. This script does the 30 findings.
"""
import json
import urllib.request

SUP = "https://xdgicslrdudsqlsudsgv.supabase.co/rest/v1"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhkZ2ljc2xyZHVkc3Fsc3Vkc2d2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MzU0Nzk1MywiZXhwIjoyMDg5MTIzOTUzfQ.clGHMQCcuBoQ7ncDdqKVNlCPlJN3zjvaUyhQ0eD2cmw"
RUN_ID = "wnbf_2026_05_11_v2"

HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal",
}

data = json.load(open("/tmp/wnbf_canonical.json"))
raw_v2 = {r["descriptor"]["isin"]: r for r in json.load(open("/tmp/wnbf_pro_grounded_v2_results.json"))["results"] if r and r.get("ok")}

rows = []
for r in data:
    isin = r["isin"]
    v2 = r.get("v2") or {}
    raw_row = raw_v2.get(isin) or {}
    citations = (raw_row.get("llm",{}) or {}).get("citations", []) or []
    row = {
        "run_id": RUN_ID,
        "isin": isin,
        "day_count_class": v2.get("day_count_class"),
        "day_count_quote": v2.get("day_count_quote"),
        "principal_repayment": v2.get("principal"),
        "amortization_schedule": v2.get("amort_schedule") or None,
        "par_call": v2.get("par_call"),
        "par_call_date": v2.get("par_call_date"),
        "make_whole_bp": v2.get("make_whole_bp"),
        "self_rated_a": v2.get("self_rated_A"),
        "self_rated_b": v2.get("self_rated_B"),
        "self_rated_c": v2.get("self_rated_C"),
        "n_queries": v2.get("n_queries"),
        "n_grounding_chunks": v2.get("n_chunks"),
        "citation_urls": citations,
        "trust_class": v2.get("trust"),
        "raw_text": v2.get("raw_text"),
        "vendor_coupon": r.get("vendor_coupon"),
        "vendor_maturity": r.get("vendor_maturity"),
        "vendor_day_count": r.get("vendor_day_count"),
        "vendor_ticker": r.get("vendor_ticker"),
        "prompt_descriptor": {
            "isin": isin,
            "openfigi_ticker": r.get("openfigi_ticker"),
            "issuer": r.get("issuer_clean"),
            "figi": r.get("figi"),
        },
        "latency_s": v2.get("latency_s"),
    }
    rows.append(row)

# Bulk upsert in one POST
req = urllib.request.Request(
    f"{SUP}/bond_static_audit_findings?on_conflict=run_id,isin",
    data=json.dumps(rows).encode(),
    headers=HEADERS,
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        print(f"HTTP {r.status}")
        print(r.read()[:500].decode())
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}")
    print(e.read()[:2000].decode())

# Verify count
req = urllib.request.Request(
    f"{SUP}/bond_static_audit_findings?run_id=eq.{RUN_ID}&select=isin",
    headers={"apikey": KEY, "Authorization": f"Bearer {KEY}", "Prefer": "count=exact"},
)
with urllib.request.urlopen(req, timeout=30) as r:
    cnt = r.headers.get("Content-Range", "?").split("/")[-1]
    print(f"\nRows in DB for run {RUN_ID}: {cnt}")
    sample = json.loads(r.read())
    print(f"sample isins: {[s['isin'] for s in sample[:5]]}")
