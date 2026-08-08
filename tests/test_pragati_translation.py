import pytest
from backend.services.translation_service import TranslationService, clean_ocr_text

def test_pragati_not_translated_to_salary():
    """Verify that पग्रɟत: पूणर्या (१००%) is cleaned to प्रगति: पूर्ण and translated to Progress: Complete (100%), NOT Salary."""
    corrupted_input = "पग्रɟत: पूणर्या (१००%)"
    cleaned = clean_ocr_text(corrupted_input)

    assert "प्रगति" in cleaned
    assert "पूर्ण" in cleaned

    translated = TranslationService.translate_paragraph(corrupted_input, source_lang="Marathi")
    print(f"\nRAW: {corrupted_input}\nCLEAN: {cleaned}\nTRANS: {translated}")

    assert "progress" in translated.lower()
    assert "salary" not in translated.lower()
