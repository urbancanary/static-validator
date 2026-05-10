"""Tests for the prospectus-extraction verifier (Layer A.5).

Fixtures use the verbatim phrasing that Gemini returned for Panama 2060
and PEMEX 2050 in the project's diagnostic test. Both bonds quote the
canonical Bond Basis phrase ("360-day year of twelve 30-day months"),
which under ISDA 2006 §4.16(f) pins ``BOND_BASIS_30_360``. Gemini
classified PEMEX correctly and Panama as ``ISMA_30_360`` — the
classification mismatch is exactly the BBG-correlated-training-bias
case this layer is designed to catch and override.
"""

from __future__ import annotations

import pytest

from static_validator.gemini_extractor import (
    AmortizationExtraction,
    CallExtraction,
    FieldExtraction,
    ProspectusExtraction,
    quote_in_pdf_text,
    verify_extraction,
)


PANAMA_QUOTE = (
    "Interest will be calculated on the basis of a 360-day year of "
    "twelve 30-day months."
)

PEMEX_QUOTE = (
    "Interest on the new securities will be calculated on the basis "
    "of a 360-day year of twelve 30-day months."
)

PEMEX_PAR_CALL_QUOTE = (
    "We may, at our option, redeem the new securities... at any time "
    "on or after July 23, 2049 (six months prior to the maturity date "
    "of the 2050 new securities), at a redemption price equal to 100% "
    "of the principal amount of the new securities then outstanding."
)

PANAMA_AMORT_QUOTE = (
    "Panama will repay the principal of the 2060 notes in three equal "
    "annual installments on July 23 of 2058, 2059 and 2060."
)


# -------- quote matching --------

class TestQuoteInPdfText:
    def test_exact_match(self):
        assert quote_in_pdf_text("hello world", "hello world")

    def test_collapses_whitespace_in_pdf(self):
        # Real PDFs often introduce line breaks mid-sentence.
        assert quote_in_pdf_text(
            "hello world",
            "...random preamble\nhello\n   world\nrandom epilogue...",
        )

    def test_collapses_whitespace_in_quote(self):
        assert quote_in_pdf_text("hello   world", "hello world")

    def test_case_insensitive(self):
        assert quote_in_pdf_text("Hello World", "hello world")

    def test_punctuation_must_match(self):
        # We deliberately don't loosen punctuation — a missing colon
        # changes meaning.
        assert not quote_in_pdf_text("hello, world", "hello world")

    def test_missing_quote(self):
        assert not quote_in_pdf_text("not in here", "some other text")

    def test_empty_quote(self):
        assert not quote_in_pdf_text("", "anything")

    def test_whitespace_only_quote(self):
        assert not quote_in_pdf_text("   ", "anything")


# -------- day_count verification --------

class TestVerifyDayCount:
    def test_pemex_quote_classifies_as_bond_basis(self):
        # PEMEX quote → BOND_BASIS_30_360 (matches Gemini's own classification).
        results = verify_extraction(
            ProspectusExtraction(
                isin="US71654QDD16",
                day_count=FieldExtraction(quote=PEMEX_QUOTE),
            ),
            pdf_text=f"...preamble... {PEMEX_QUOTE} ...epilogue...",
        )
        assert len(results) == 1
        r = results[0]
        assert r.field == "day_count"
        assert r.verified is True
        assert r.canonical_value == "BOND_BASIS_30_360"

    def test_panama_quote_overrides_gemini_isma_misclassification(self):
        # The smoking-gun test: the Panama quote IS the canonical Bond
        # Basis phrase under ISDA 2006 §4.16(f). Gemini labelled it
        # ISMA_30_360 — that label never enters the extraction (no
        # classification field exists on FieldExtraction by design),
        # and our deterministic re-classifier returns BOND_BASIS_30_360.
        results = verify_extraction(
            ProspectusExtraction(
                isin="US698299BL70",
                day_count=FieldExtraction(quote=PANAMA_QUOTE),
            ),
            pdf_text=f"...{PANAMA_QUOTE}...",
        )
        r = results[0]
        assert r.verified is True
        assert r.canonical_value == "BOND_BASIS_30_360"
        assert "deterministically" in r.note

    def test_unverifiable_quote_rejected(self):
        results = verify_extraction(
            ProspectusExtraction(
                isin="US698299BL70",
                day_count=FieldExtraction(
                    quote="Interest accrues on a fictional convention X/Y/Z.",
                ),
            ),
            pdf_text="...completely unrelated PDF text...",
        )
        r = results[0]
        assert r.verified is False
        assert r.canonical_value is None
        assert "not found" in r.note

    def test_verified_quote_with_silent_subvariant(self):
        # Quote is real (verified) but doesn't match any canonical phrase
        # pattern → prospectus-silent on the sub-variant. The verifier
        # must NOT pick a default; it routes to contested-field handling.
        silent_quote = "Interest will be paid on each interest payment date."
        results = verify_extraction(
            ProspectusExtraction(
                isin="US698299BL70",
                day_count=FieldExtraction(quote=silent_quote),
            ),
            pdf_text=f"...{silent_quote}...",
        )
        r = results[0]
        assert r.verified is True
        assert r.canonical_value is None
        assert "silent" in r.note or "contested" in r.note

    def test_eurobond_basis_phrase_resolves_to_isda_30e(self):
        quote = (
            "Interest is calculated using Eurobond Basis as defined in "
            "the 2006 ISDA Definitions."
        )
        results = verify_extraction(
            ProspectusExtraction(
                isin="XS1234567890",
                day_count=FieldExtraction(quote=quote),
            ),
            pdf_text=f"...{quote}...",
        )
        assert results[0].canonical_value == "ISDA_30E_360"

    def test_panama_quote_resilient_to_pdf_linebreaks(self):
        # Real PDF text frequently breaks "30-day\nmonths" across lines.
        wrapped = (
            "Interest will be\ncalculated on the basis of a 360-day year\n"
            "of twelve 30-day\nmonths."
        )
        results = verify_extraction(
            ProspectusExtraction(
                isin="US698299BL70",
                day_count=FieldExtraction(quote=PANAMA_QUOTE),
            ),
            pdf_text=f"...preamble...\n{wrapped}\n...epilogue...",
        )
        assert results[0].verified is True
        assert results[0].canonical_value == "BOND_BASIS_30_360"


# -------- structural fields --------

class TestVerifyStructural:
    def test_panama_amortization_verified(self):
        results = verify_extraction(
            ProspectusExtraction(
                isin="US698299BL70",
                amortization=AmortizationExtraction(
                    is_bullet=False,
                    schedule=[
                        ("2058-07-23", 33.33),
                        ("2059-07-23", 33.33),
                        ("2060-07-23", 33.34),
                    ],
                    quote=PANAMA_AMORT_QUOTE,
                ),
            ),
            pdf_text=f"...{PANAMA_AMORT_QUOTE}...",
        )
        r = results[0]
        assert r.field == "amortization"
        assert r.verified is True
        assert r.structural_value["is_bullet"] is False
        assert len(r.structural_value["schedule"]) == 3

    def test_amortization_quote_missing_rejects_structure(self):
        results = verify_extraction(
            ProspectusExtraction(
                isin="US698299BL70",
                amortization=AmortizationExtraction(
                    is_bullet=False,
                    schedule=[("2058-07-23", 33.33)],
                    quote="Hallucinated amortization sentence not in document.",
                ),
            ),
            pdf_text="...completely unrelated PDF text...",
        )
        r = results[0]
        assert r.verified is False
        assert r.structural_value is None

    def test_pemex_par_call_verified(self):
        results = verify_extraction(
            ProspectusExtraction(
                isin="US71654QDD16",
                call=CallExtraction(
                    has_make_whole=True,
                    has_par_call=True,
                    par_call_date="2049-07-23",
                    treasury_spread_bps=50,
                    quote=PEMEX_PAR_CALL_QUOTE,
                ),
            ),
            pdf_text=f"...{PEMEX_PAR_CALL_QUOTE}...",
        )
        r = results[0]
        assert r.field == "call"
        assert r.verified is True
        assert r.structural_value["has_par_call"] is True
        assert r.structural_value["par_call_date"] == "2049-07-23"


# -------- end-to-end: a single ProspectusExtraction, multiple fields --------

class TestEndToEnd:
    def test_panama_full_extraction(self):
        # Model emits day_count + amortization. Verifier checks both
        # against the same PDF text and produces two results.
        pdf_text = (
            f"Description of the Notes — General. {PANAMA_QUOTE} "
            f"Description of the Notes — Principal Repayment. {PANAMA_AMORT_QUOTE}"
        )
        results = verify_extraction(
            ProspectusExtraction(
                isin="US698299BL70",
                day_count=FieldExtraction(quote=PANAMA_QUOTE),
                amortization=AmortizationExtraction(
                    is_bullet=False,
                    schedule=[
                        ("2058-07-23", 33.33),
                        ("2059-07-23", 33.33),
                        ("2060-07-23", 33.34),
                    ],
                    quote=PANAMA_AMORT_QUOTE,
                ),
            ),
            pdf_text=pdf_text,
        )
        assert {r.field for r in results} == {"day_count", "amortization"}
        assert all(r.verified for r in results)
        dc = next(r for r in results if r.field == "day_count")
        # The whole point: Bond Basis, even though Gemini labelled it ISMA.
        assert dc.canonical_value == "BOND_BASIS_30_360"
