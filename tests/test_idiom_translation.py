"""Tests for Marathi idiom / proverb meaning-based translation (never transliteration)."""
import pytest
from backend.services.translation_service import (
    TranslationService,
    MARATHI_IDIOM_GLOSSARY,
    clean_ocr_text,
)


class TestIdiomTranslation:
    """Verify idioms and proverbs are translated by meaning, not transliterated."""

    def test_ati_tithe_maati(self):
        result = TranslationService.translate_paragraph("अति तिथे माती", "marathi")
        assert "Excess" in result or "harmful" in result
        assert "ati" not in result.lower()
        assert "maati" not in result.lower()

    def test_perave_tase_ugavte(self):
        result = TranslationService.translate_paragraph("पेरावे तसे उगवते", "marathi")
        assert "sow" in result.lower() or "reap" in result.lower()

    def test_uthal_panyala(self):
        result = TranslationService.translate_paragraph("उथळ पाण्याला खळखळाट जास्त", "marathi")
        assert "Empty vessels" in result or "noise" in result

    def test_durun_dongar(self):
        result = TranslationService.translate_paragraph("दुरून डोंगर साजरे", "marathi")
        assert "grass" in result.lower() or "greener" in result.lower()

    def test_ayatya_bilavar(self):
        result = TranslationService.translate_paragraph("आयत्या बिळावर नागोबा", "marathi")
        assert "advantage" in result.lower() or "effort" in result.lower()
        assert "nagoba" not in result.lower()

    def test_government_fixed_expression(self):
        result = TranslationService.translate_paragraph("शासन निर्णय", "marathi")
        assert result == "Government Resolution"

    def test_satyamev_jayate(self):
        result = TranslationService.translate_paragraph("सत्यमेव जयते", "marathi")
        assert "Truth" in result or "triumphs" in result


class TestOCRPreprocessing:
    """Verify OCR artifact cleanup before translation."""

    def test_remove_black_squares(self):
        assert clean_ocr_text("अति ■ तिथे ■ माती") == "अति तिथे माती"

    def test_remove_replacement_chars(self):
        assert clean_ocr_text("सरकार�ी आदेश") == "सरकारी आदेश"

    def test_remove_question_marks(self):
        assert clean_ocr_text("शासन ??? निर्णय") == "शासन निर्णय"

    def test_unicode_normalization(self):
        result = clean_ocr_text("  शासन  निर्णय  ")
        assert result == "शासन निर्णय"



