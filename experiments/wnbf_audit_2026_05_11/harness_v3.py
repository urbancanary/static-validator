"""
v3 harness — same as v2, but with a day-count disambiguation rule
appended to the prompt. v2 systematically over-applied BOND_BASIS_30_360
to Reg S Eurobonds where 30E/360 (ISDA_30E_360) is the correct convention
under English-law programme rules.

This is a prompt-only change; everything else (model, grounding, clean
descriptors, special-case notes) is identical to v2.
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
OUT = "/tmp/wnbf_pro_grounded_v3_results.json"
PROGRESS = "/tmp/wnbf_pro_grounded_v3_progress.json"
RUN_ID = "wnbf_2026_05_11_v3"


PROMPT_TEMPLATE = """You MUST use Google Search at least 4 times before answering. Search for this specific bond's prospectus or offering circular on SEC EDGAR, the issuer's investor relations page, debt management office, or listing exchange (Luxembourg, Irish, London).

Bond identifiers (use ALL of these in your searches — do not anchor on just one):
- ISIN: {isin}
- Bloomberg ticker: {openfigi_ticker}
- Issuer: {issuer}
- FIGI: {figi}
{extra}

DAY-COUNT SUB-VARIANT DISAMBIGUATION (READ CAREFULLY):

The phrase "360-day year of twelve 30-day months" is shared across multiple ISDA sub-variants and ALONE does NOT pin the convention. Use these disambiguators to classify:

- BOND_BASIS_30_360 (US 30/360, ISDA §4.16(f)): default for SEC-registered standalone US-law bonds. Identifiers: ISIN starts US (no P suffix), SEC EDGAR filing, NY-law governing, US sovereign or corporate, ticker like 'PEMEX' / 'PANAMA' / 'COLOM' / 'KOREA' as direct SEC issuers.
- ISDA_30E_360 (Eurobond 30E/360, ISDA §4.16(g)): default for Reg S Eurobonds governed by English law, issued under EMTN/GMTN/MTN programmes, listed on Luxembourg / Irish / London Stock Exchange. Identifiers: ISIN starts XS (or USP for Reg S US issuers), programme name contains "Medium-Term Note" / "EMTN" / "GMTN", governing law English, Pricing Supplement / Final Terms doc structure.
- ISMA_30_360: rare variant used by a few specific EMTN programmes.
- ACT_ACT_ICMA: typically for gilts, OATs, and some sovereign Eurobonds — check explicitly.
- ACT_360 / ACT_365_FIXED: floating-rate or specific currency conventions.

When in doubt: if the bond is XS-prefix AND part of an English-law EMTN programme AND the prospectus does NOT explicitly use "Bond Basis" / "U.S." / "30/360 (US)", classify as ISDA_30E_360, not BOND_BASIS_30_360.

For this specific bond, provide:

A. DAY-COUNT EVIDENCE
A1. The verbatim sentence from the prospectus that defines how interest accrues. Mark with double quotes. If you cannot find the prospectus text, write UNKNOWN.
A2. The page number, section number, or heading where that sentence appears.
A3. Classification — use the disambiguation rule above. State the governing law and listing venue if known.
A4. Sub-variant pinpointed in the prospectus, or your inference (cite reason: governing law / listing venue / programme convention).

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

EXTRA_NOTES = {
    "US91086QAZ19": "- Note: This is Mexico 5.75% NOTES DUE OCTOBER 12, **2110** (the 100-year bond). Bloomberg displays the maturity as '10/12/10' where YY=10 means the year 2110, NOT 2010.",
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
    print(f"[{time.strftime('%H:%M:%S')}] v3 run — {len(descs)} bonds, {MODEL}+grounding, {WORKERS} workers, prompt: day-count-disambiguation")
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
                import re
                m = re.search(r"A3[.:\s]+([^\n]{0,80})", text)
                dc = m.group(1).strip() if m else "?"
                m = re.search(r"B1[.:\s]+([^\n]+)", text)
                pr = "AMORT" if m and ("installment" in m.group(1).lower() or "amortiz" in m.group(1).lower()) else "bullet"
                print(f"  [{done:2d}/30] {isin}  q={llm['n_queries']:>2d} cit={llm['n_chunks']:>2d}  dc={dc[:30]:30s} {pr:6s}  ({llm['latency_s']:>5.1f}s)")
            else:
                print(f"  [{done:2d}/30] {isin}  ERROR: {r.get('error')[:80]}")
            json.dump({"results": results, "done": done}, open(PROGRESS, "w"))
    json.dump({"results": results}, open(OUT, "w"), indent=2)
    print(f"\nSaved {OUT}")


if __name__ == "__main__":
    main()
