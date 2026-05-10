"""Layer A.5: verifier for prospectus extractions emitted by an LLM.

The module is intentionally pure — it accepts a structured extraction
plus the source PDF text and emits a list of ``VerificationResult``s.
The actual LLM call (Gemini, or any other model) lives upstream; this
layer's job is to make the LLM's output safe to feed into the canonical
pipeline.

The architecture rests on one operational finding (see project docs):

    Frontier multimodal models reliably retrieve **verbatim quotes** and
    **structural facts** (call schedules, amortization tranches) from
    bond prospectuses. They do NOT reliably classify *conventions*
    (day_count, calendar, BDC) — their classification labels are
    correlated with vendor coding that has its own drift from the
    underlying document.

So the verifier:

1. Treats every quote as a claim that must be regex-matched against the
   PDF text. Unverified quotes are rejected.
2. **Discards the model's day_count classification entirely** and
   re-derives it deterministically from the verified quote, via
   ``adapter.classify_day_count_phrase``.
3. Trusts structural facts (bullet vs amortizing, call dates, MW spread)
   only after their associated quote is verified.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from .adapter import classify_day_count_phrase


SourceRating = Literal[
    "prospectus_quoted",
    "secondary_summary",
    "general_market_knowledge",
    "guess",
]


@dataclass
class FieldExtraction:
    """One field's verbatim evidence from a prospectus extraction.

    The model's own classification, if it emitted one, is deliberately
    NOT stored on this record. Day-count classification is re-derived
    from the verified quote in ``verify_extraction``.
    """
    quote: str
    page_or_section: str | None = None
    source_rating: SourceRating | None = None


@dataclass
class AmortizationExtraction:
    """Structural extraction for the principal-repayment field."""
    is_bullet: bool
    schedule: list[tuple[str, float]] = field(default_factory=list)
    quote: str | None = None
    page_or_section: str | None = None
    source_rating: SourceRating | None = None


@dataclass
class CallExtraction:
    """Structural extraction for call optionality."""
    has_make_whole: bool = False
    has_par_call: bool = False
    par_call_date: str | None = None
    treasury_spread_bps: int | None = None
    quote: str | None = None
    page_or_section: str | None = None
    source_rating: SourceRating | None = None


@dataclass
class ProspectusExtraction:
    """A model's extraction for a single bond, as emitted upstream.

    Populating this is the caller's job (Gemini API call, file load,
    manual transcription). The verifier doesn't care how it got built.
    """
    isin: str
    day_count: FieldExtraction | None = None
    amortization: AmortizationExtraction | None = None
    call: CallExtraction | None = None


@dataclass
class VerificationResult:
    field: str
    quote: str | None
    verified: bool
    canonical_value: str | None = None
    structural_value: object | None = None
    note: str = ""


def _normalise_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def quote_in_pdf_text(quote: str, pdf_text: str) -> bool:
    """Whitespace-insensitive, case-insensitive substring check.

    PDF text extraction frequently introduces line breaks and stray
    spaces that wouldn't appear in a model's reproduced quote, so
    matching after whitespace collapse is the load-bearing relaxation.
    Punctuation must still match exactly — we don't loosen that, because
    a missing colon or comma can change the meaning of a financial
    sentence.
    """
    if not quote.strip():
        return False
    return _normalise_for_match(quote) in _normalise_for_match(pdf_text)


def verify_extraction(
    extraction: ProspectusExtraction,
    pdf_text: str,
) -> list[VerificationResult]:
    """Verify each quoted field in the extraction against ``pdf_text``.

    Returns one ``VerificationResult`` per checked field. The day_count
    result, if verified, carries the *deterministically re-derived*
    canonical enum — never whatever label the model attached upstream.
    """
    results: list[VerificationResult] = []

    if extraction.day_count is not None:
        dc = extraction.day_count
        verified = quote_in_pdf_text(dc.quote, pdf_text)
        if not verified:
            results.append(VerificationResult(
                field="day_count",
                quote=dc.quote,
                verified=False,
                note="quote not found in PDF text; reject",
            ))
        else:
            canonical = classify_day_count_phrase(dc.quote)
            if canonical is not None:
                results.append(VerificationResult(
                    field="day_count",
                    quote=dc.quote,
                    verified=True,
                    canonical_value=canonical,
                    note="quote verified; classified deterministically from canonical phrase pattern",
                ))
            else:
                results.append(VerificationResult(
                    field="day_count",
                    quote=dc.quote,
                    verified=True,
                    canonical_value=None,
                    note=(
                        "quote verified but did not match any canonical "
                        "phrase pattern; treat as prospectus-silent on "
                        "sub-variant and route to contested-field handling"
                    ),
                ))

    if extraction.amortization is not None:
        am = extraction.amortization
        if am.quote is None:
            results.append(VerificationResult(
                field="amortization",
                quote=None,
                verified=False,
                note="no quote provided; cannot verify",
            ))
        else:
            verified = quote_in_pdf_text(am.quote, pdf_text)
            if verified:
                results.append(VerificationResult(
                    field="amortization",
                    quote=am.quote,
                    verified=True,
                    structural_value={
                        "is_bullet": am.is_bullet,
                        "schedule": am.schedule,
                    },
                    note="quote verified; structural facts trusted",
                ))
            else:
                results.append(VerificationResult(
                    field="amortization",
                    quote=am.quote,
                    verified=False,
                    note="quote not found in PDF text; reject structural facts",
                ))

    if extraction.call is not None:
        c = extraction.call
        if c.quote is None:
            results.append(VerificationResult(
                field="call",
                quote=None,
                verified=False,
                note="no quote provided; cannot verify",
            ))
        else:
            verified = quote_in_pdf_text(c.quote, pdf_text)
            if verified:
                results.append(VerificationResult(
                    field="call",
                    quote=c.quote,
                    verified=True,
                    structural_value={
                        "has_make_whole": c.has_make_whole,
                        "has_par_call": c.has_par_call,
                        "par_call_date": c.par_call_date,
                        "treasury_spread_bps": c.treasury_spread_bps,
                    },
                    note="quote verified; structural facts trusted",
                ))
            else:
                results.append(VerificationResult(
                    field="call",
                    quote=c.quote,
                    verified=False,
                    note="quote not found in PDF text; reject structural facts",
                ))

    return results


__all__ = [
    "AmortizationExtraction",
    "CallExtraction",
    "FieldExtraction",
    "ProspectusExtraction",
    "VerificationResult",
    "quote_in_pdf_text",
    "verify_extraction",
]
