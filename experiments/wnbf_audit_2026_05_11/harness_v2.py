"""
WNBF Pro+grounding rerun, v2: clean descriptor block using
  - ISIN
  - openfigi_ticker (Bloomberg-canonical)
  - bond_identity.issuer (clean issuer name, no truncation)
  - figi (hard secondary identifier)
"""
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
MODEL = "gemini-3.1-pro-preview"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_KEY}"
WORKERS = 6
DESC = "/tmp/wnbf_descriptors_clean.json"
OUT = "/tmp/wnbf_pro_grounded_v2_results.json"
PROGRESS = "/tmp/wnbf_pro_grounded_v2_progress.json"

PROMPT_TEMPLATE = """You MUST use Google Search at least 4 times before answering. Search for this specific bond's prospectus or offering circular on SEC EDGAR, the issuer's investor relations page, debt management office, or listing exchange (Luxembourg, Irish, London).

Bond identifiers (use ALL of these in your searches — do not anchor on just one):
- ISIN: {isin}
- Bloomberg ticker: {openfigi_ticker}
- Issuer: {issuer}
- FIGI: {figi}
{extra}

For this specific bond, provide:

A. DAY-COUNT EVIDENCE
A1. The verbatim sentence from the prospectus that defines how interest accrues. Mark with double quotes. If you cannot find the prospectus text, write UNKNOWN.
A2. The page number, section number, or heading where that sentence appears.
A3. Classification: BOND_BASIS_30_360 | ISDA_30E_360 | ISMA_30_360 | ACT_ACT_ICMA | ACT_ACT_ISDA | ACT_360 | ACT_365_FIXED | ACT_365_25 | UNKNOWN
A4. Was the sub-variant pinpointed in the prospectus, or is it your inference?

B. PRINCIPAL REPAYMENT
B1. Single bullet at maturity, or scheduled installments?
B2. If installments: list each (date, percentage of original principal).
B3. Verbatim sentence from the prospectus + page reference.

C. CALL OPTIONALITY
C1. Make-whole call, par call, both, or neither?
C2. If par call: the date it begins, with verbatim phrase.
C3. If make-whole: the comparable-Treasury spread in basis points, with verbatim phrase.

D. SOURCE SELF-RATING
A, B, C each: prospectus_quoted | secondary_summary | general_market_knowledge | guess

E. EVIDENCE TRAIL
List the URLs of the documents you actually drew from.
"""

# Special-case annotations for known disambiguation hazards
EXTRA_NOTES = {
    "US91086QAZ19": "- Note: This is the Mexico 5.75% NOTES DUE OCTOBER 12, **2110** (the 100-year bond). Bloomberg displays the maturity as '10/12/10' where YY=10 means the year 2110, NOT 2010.",
}


def call(d):
    isin = d["isin"]
    prompt = PROMPT_TEMPLATE.format(
        isin=isin,
        openfigi_ticker=d.get("openfigi_ticker") or "n/a",
        issuer=d.get("issuer") or "n/a",
        figi=d.get("figi") or "n/a",
        extra=EXTRA_NOTES.get(isin, ""),
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 4000},
        "tools": [{"googleSearch": {}}],
    }
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(),
                                  headers={"Content-Type":"application/json"}, method="POST")
    t0 = time.time()
    raw = json.loads(urllib.request.urlopen(req, timeout=600).read())
    dt = time.time() - t0
    c = (raw.get("candidates") or [{}])[0]
    parts = c.get("content", {}).get("parts", [])
    text = "\n".join(p.get("text","") for p in parts if "text" in p)
    gm = c.get("groundingMetadata", {})
    return {
        "text": text,
        "latency_s": round(dt, 1),
        "usage": raw.get("usageMetadata", {}),
        "n_queries": len(gm.get("webSearchQueries", [])),
        "queries": gm.get("webSearchQueries", []),
        "n_chunks": len(gm.get("groundingChunks", [])),
        "citations": [g["web"].get("uri","") for g in gm.get("groundingChunks", []) if "web" in g][:20],
    }


def process(idx, d):
    try:
        return {"idx": idx, "descriptor": d, "llm": call(d), "ok": True}
    except Exception as e:
        return {"idx": idx, "descriptor": d, "error": str(e), "ok": False}


def main():
    descs = json.load(open(DESC))
    print(f"[{time.strftime('%H:%M:%S')}] WNBF v2 rerun — {len(descs)} bonds, {MODEL}+grounding, {WORKERS} workers")
    results = [None]*len(descs)
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(process, i, d): i for i, d in enumerate(descs)}
        for fut in as_completed(futs):
            i = futs[fut]
            r = fut.result()
            results[i] = r
            done += 1
            isin = descs[i]["isin"]
            if r.get("ok"):
                llm = r["llm"]
                text = llm.get("text","")
                tl = text.lower()
                amort = "AMORT" if ("installment" in tl or "amortiz" in tl) and not ("single bullet" in tl[:tl.find("c.")] if "c." in tl else False) else "bullet"
                # better: just look for B1 line
                import re
                m = re.search(r"B1[.:\s]+([^\n]+)", text)
                if m: amort = "AMORT" if ("installment" in m.group(1).lower() or "amortiz" in m.group(1).lower()) else "bullet"
                par = "PAR" if "par call" in tl and "no par call" not in tl else "no-par"
                print(f"  [{done:2d}/30] {isin}  q={llm['n_queries']:>2d} cit={llm['n_chunks']:>2d}  "
                      f"{amort:6s} {par:7s}  ({llm['latency_s']:>5.1f}s)")
            else:
                print(f"  [{done:2d}/30] {isin}  ERROR: {r.get('error')[:80]}")
            json.dump({"results": results, "done": done}, open(PROGRESS, "w"))
    json.dump({"results": results}, open(OUT, "w"), indent=2)
    print(f"\nSaved {OUT}")


if __name__ == "__main__":
    main()
