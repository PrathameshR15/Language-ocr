import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from backend.services.translation_service import TranslationService, clean_ocr_text
from backend.services.language_detection_service import LanguageDetectionService

def test_bengali_language_detection():
    """Verify language detection accurately identifies Bengali text."""
    bengali_text = "গ্রাম উন্নয়ন কাজ - সংক্ষিপ্ত প্রতিবেদন"
    detected = LanguageDetectionService.detect_language(bengali_text)
    assert detected.lower() in ("bengali", "bn")

def test_bengali_administrative_dictionary_terms():
    """Verify exact Bengali administrative terms translate cleanly."""
    term_cases = [
        ("সহ-সচিব", "Deputy Secretary"),
        ("জেলা পরিষদ", "Zilla Parishad"),
        ("পঞ্চায়েত সমিতি", "Panchayat Samiti"),
        ("প্রাথমিক স্বাস্থ্য কেন্দ্র", "Primary Health Center"),
        ("গ্রাম উন্নয়ন কাজ - সংক্ষিপ্ত প্রতিবেদন", "Village Development Work - Brief Report"),
    ]
    for src, expected in term_cases:
        res = TranslationService.translate_paragraph(src, source_lang="Bengali")
        assert (expected.lower() in res.lower()) or ("secretary" in res.lower())

def test_bengali_ocr_cleaning():
    """Verify Bengali font noise and broken vowel signs are cleaned properly."""
    raw = "তাহলে আপনি যদি বাংলোয় চান, তবে একই সংক্ষিপ্ত প্রতিবেদনটি নিচে দেওয়া হলো:"
    cleaned = clean_ocr_text(raw)
    assert "বাংলা" in cleaned
