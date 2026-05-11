"""
Build the canonical WNBF dataset combining:
  - vendor static (from /tmp/wnbf_bonds.json — basic Supabase bonds table)
  - clean descriptors (bond_identity issuer, openfigi_ticker, figi)
  - V1 parsed result (Pro+grounding, original descriptors)
  - V2 parsed result (Pro+grounding, clean openfigi descriptors)
  - trust flags
  - vendor diff per structural field

Save to /tmp/wnbf_canonical.json + /tmp/wnbf_canonical.csv for review.
"""
import json
import csv
import re


def parse_structural(text):
    """Extract structural facts from A/B/C/D prose."""
    t = text or ""
    out = {
        "day_count_class": None,
        "day_count_quote": None,
        "principal": "UNKNOWN",
        "par_call": "UNKNOWN",
        "par_call_date": None,
        "make_whole_bp": None,
        "amort_schedule": [],
        "self_rated_A": None,
        "self_rated_B": None,
        "self_rated_C": None,
    }
    # day-count classification
    for cls in ["BOND_BASIS_30_360","ISDA_30E_360","ISMA_30_360","ACT_ACT_ICMA","ACT_ACT_ISDA","ACT_360","ACT_365_FIXED","ACT_365_25"]:
        if cls in t:
            out["day_count_class"] = cls
            break
    # day-count verbatim (A1)
    m = re.search(r'A1[.:\s]+(?:Verbatim[^"]*)?\s*"([^"]{20,300})"', t, re.I)
    if m: out["day_count_quote"] = m.group(1).strip()
    # principal (B1)
    m = re.search(r"B1[.:\s]+([^\n]+)", t)
    if m:
        b1 = m.group(1).lower()
        if "installment" in b1 or "amortiz" in b1:
            out["principal"] = "AMORTIZING"
        elif "bullet" in b1:
            out["principal"] = "BULLET"
    # amortization schedule (B2)
    schedule = re.findall(r"(\d{4}-\d{2}-\d{2}|\w+ \d{1,2},? \d{4}|\w+ \d{1,2} of \d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})[^\n%]*(\d{1,3}\.?\d*)\s*%", t[:3000])
    out["amort_schedule"] = [{"date": d.strip(), "pct": p} for d,p in schedule[:6]]
    # par call (C1)
    tl = t.lower()
    m = re.search(r"C1[.:\s]+([^\n]+)", t)
    if m:
        c1 = m.group(1).lower()
        if "neither" in c1 or "no call" in c1:
            out["par_call"] = "NEITHER"
        elif "both" in c1 or "par call" in c1:
            out["par_call"] = "PAR_CALL" if "par call" in c1 else "MAKE_WHOLE_ONLY"
            if "make-whole" in c1 and "par call" in c1:
                out["par_call"] = "BOTH"
        elif "make-whole" in c1:
            out["par_call"] = "MAKE_WHOLE_ONLY"
    # par call date (C2)
    m = re.search(r"C2[.:\s]+([^\n]+)", t)
    if m:
        c2 = m.group(1)
        date_m = re.search(r"(\w+ \d{1,2},? \d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})", c2)
        if date_m: out["par_call_date"] = date_m.group(1)
    # make-whole bp (C3)
    mw_match = re.search(r"(\d{1,3})\s*basis\s*points?", t, re.I)
    if mw_match: out["make_whole_bp"] = int(mw_match.group(1))
    # self-ratings — handle "* A: prospectus_quoted", "A. prospectus_quoted", "**A:** prospectus_quoted", etc.
    for sec in ["A","B","C"]:
        # Look in the D. SOURCE SELF-RATING section preferentially
        m = re.search(rf"(?:^|\n)\s*[*\-•]?\s*\*{{0,2}}\s*{sec}[.:\s\*]+(prospectus_quoted|secondary_summary|general_market_knowledge|guess)", t, re.I | re.M)
        if m: out[f"self_rated_{sec}"] = m.group(1).lower()
    return out


def trust_score(parsed, n_queries, n_chunks):
    """Trust based on grounding metadata, not text claims."""
    if n_queries == 0:
        return "untrusted_no_grounding"
    if parsed["self_rated_A"] == "prospectus_quoted" and n_chunks > 0:
        return "high_prospectus_quoted_with_chunks"
    if parsed["self_rated_A"] == "prospectus_quoted":
        return "medium_prospectus_quoted_no_chunks"
    if parsed["self_rated_A"] == "secondary_summary":
        return "low_secondary_summary"
    if parsed["self_rated_A"] in ("general_market_knowledge","guess"):
        return "untrusted_general_knowledge"
    return "unrated"


vendors = {b["isin"]: b for b in json.load(open("/tmp/wnbf_bonds.json"))}
descs = {d["isin"]: d for d in json.load(open("/tmp/wnbf_descriptors_clean.json"))}
v1 = {r["vendor"]["isin"]: r for r in json.load(open("/tmp/wnbf_pro_grounded_results.json"))["raw_results"]}
v2 = {r["descriptor"]["isin"]: r for r in json.load(open("/tmp/wnbf_pro_grounded_v2_results.json"))["results"] if r and r.get("ok")}

dataset = []
for isin in sorted(vendors.keys()):
    v = vendors[isin]
    d = descs.get(isin, {})
    row = {
        "isin": isin,
        # vendor static
        "vendor_ticker": v.get("ticker"),
        "vendor_coupon": v.get("coupon"),
        "vendor_maturity": v.get("maturity_date"),
        "vendor_issue_date": v.get("issue_date"),
        "vendor_day_count": v.get("day_count"),
        "vendor_country": v.get("country"),
        # clean descriptors from bond_identity / bond_reference
        "openfigi_ticker": d.get("openfigi_ticker"),
        "figi": d.get("figi"),
        "issuer_clean": d.get("issuer"),
        "issuer_description": d.get("issuer_description"),
        "openfigi_name": d.get("openfigi_name"),
    }
    # v1
    v1r = v1.get(isin)
    if v1r:
        v1_llm = v1r.get("llm", {})
        v1_text = v1_llm.get("text","") if isinstance(v1_llm, dict) else ""
        v1_q = len(v1_llm.get("web_queries", [])) if isinstance(v1_llm, dict) else 0
        v1_c = v1_llm.get("grounding_chunks_count", 0) if isinstance(v1_llm, dict) else 0
        v1_p = parse_structural(v1_text)
        row["v1"] = {**v1_p, "n_queries": v1_q, "n_chunks": v1_c,
                     "latency_s": v1_llm.get("latency_s") if isinstance(v1_llm, dict) else None,
                     "trust": trust_score(v1_p, v1_q, v1_c)}
    # v2
    v2r = v2.get(isin)
    if v2r:
        v2_llm = v2r["llm"]
        v2_text = v2_llm.get("text","")
        v2_q = v2_llm.get("n_queries", 0)
        v2_c = v2_llm.get("n_chunks", 0)
        v2_p = parse_structural(v2_text)
        row["v2"] = {**v2_p, "n_queries": v2_q, "n_chunks": v2_c,
                     "latency_s": v2_llm.get("latency_s"),
                     "trust": trust_score(v2_p, v2_q, v2_c),
                     "raw_text": v2_text}
    dataset.append(row)


# Save canonical
json.dump(dataset, open("/tmp/wnbf_canonical.json","w"), indent=2)

# CSV for spreadsheet review
fieldnames = [
    "isin","openfigi_ticker","issuer_clean","vendor_coupon","vendor_maturity",
    "vendor_day_count",
    "v1_dc","v1_principal","v1_par","v1_q","v1_trust",
    "v2_dc","v2_principal","v2_par","v2_q","v2_trust",
    "agreement_dc","agreement_principal","agreement_par",
    "structural_correction_vs_vendor",
]
with open("/tmp/wnbf_canonical.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for r in dataset:
        v1p = r.get("v1", {})
        v2p = r.get("v2", {})
        v_dc = r.get("vendor_day_count") or ""
        v2_dc = v2p.get("day_count_class") or ""
        v2_pr = v2p.get("principal") or "?"
        # vendor_day_count is "30/360" — map to BOND_BASIS for comparison
        vendor_dc_norm = "BOND_BASIS_30_360" if v_dc == "30/360" else v_dc
        agreement_dc = "agree" if v2_dc == vendor_dc_norm else f"disagree({v_dc} vs {v2_dc})"
        # Structural correction = v2 says AMORT and vendor would assume bullet
        correction = ""
        if v2_pr == "AMORTIZING":
            correction = "VENDOR_LIKELY_WRONG_FLAG_AS_BULLET"
        elif v1p.get("principal") and v2_pr and v1p.get("principal") != v2_pr:
            correction = f"V1_V2_DISAGREE({v1p.get('principal')}→{v2_pr})"
        w.writerow({
            "isin": r["isin"],
            "openfigi_ticker": r["openfigi_ticker"],
            "issuer_clean": r["issuer_clean"],
            "vendor_coupon": r["vendor_coupon"],
            "vendor_maturity": r["vendor_maturity"],
            "vendor_day_count": v_dc,
            "v1_dc": v1p.get("day_count_class") or "",
            "v1_principal": v1p.get("principal") or "",
            "v1_par": v1p.get("par_call") or "",
            "v1_q": v1p.get("n_queries"),
            "v1_trust": v1p.get("trust") or "",
            "v2_dc": v2_dc,
            "v2_principal": v2_pr,
            "v2_par": v2p.get("par_call") or "",
            "v2_q": v2p.get("n_queries"),
            "v2_trust": v2p.get("trust") or "",
            "agreement_dc": agreement_dc,
            "agreement_principal": "agree" if v1p.get("principal") == v2_pr else "disagree",
            "agreement_par": "agree" if v1p.get("par_call") == v2p.get("par_call") else "disagree",
            "structural_correction_vs_vendor": correction,
        })

# Summary
n = len(dataset)
v2_trust_buckets = {}
for r in dataset:
    t = r.get("v2",{}).get("trust", "missing")
    v2_trust_buckets[t] = v2_trust_buckets.get(t,0) + 1
print(f"\n=== Canonical dataset: {n} bonds ===")
print(f"\nV2 trust distribution:")
for k,v in sorted(v2_trust_buckets.items(), key=lambda kv: -kv[1]):
    print(f"  {k:42s} : {v:>3d}")
amort = [r for r in dataset if r.get("v2",{}).get("principal") == "AMORTIZING"]
print(f"\nAMORTIZING flagged by v2: {len(amort)}")
for r in amort:
    print(f"  {r['isin']}  {r['openfigi_ticker']}  ({r['issuer_clean']})")

dc_disagree = []
for r in dataset:
    v2_dc = r.get("v2",{}).get("day_count_class")
    v_dc = r.get("vendor_day_count")
    if v2_dc and v_dc:
        vendor_norm = "BOND_BASIS_30_360" if v_dc == "30/360" else v_dc
        if v2_dc != vendor_norm:
            dc_disagree.append((r["isin"], r["openfigi_ticker"], v_dc, v2_dc))
print(f"\nVendor vs V2 day-count disagreements: {len(dc_disagree)}")
for x in dc_disagree:
    print(f"  {x[0]} {x[1]}  vendor={x[2]}  v2={x[3]}")

untrusted = [r for r in dataset if r.get("v2",{}).get("trust","").startswith("untrusted")]
print(f"\nV2 untrusted (no grounding or guess-based): {len(untrusted)}")
for r in untrusted:
    print(f"  {r['isin']}  {r['openfigi_ticker']}  trust={r['v2']['trust']}")

print(f"\nSaved /tmp/wnbf_canonical.json  ({len(dataset)} rows)")
print(f"Saved /tmp/wnbf_canonical.csv  (spreadsheet-friendly)")
