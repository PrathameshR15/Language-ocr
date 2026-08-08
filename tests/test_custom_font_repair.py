import pytest
from backend.services.translation_service import TranslationService, clean_ocr_text

def test_custom_font_cmap_digit_repair():
    """Verify repair of Shree-Lipi / KrutiDev / DVB-TT font CMAP digit corruption like न9न -> नवीन."""
    corrupted_text = "जिलह् परिषद शाळा न9न इमरिित उत्तरिाभिमुख पशम्चि बाजिूची खोली"
    cleaned = clean_ocr_text(corrupted_text)

    assert "नवीन" in cleaned
    assert "नवीनन" not in cleaned
    assert "जिल्हा" in cleaned
    assert "इमारत" in cleaned
    assert "पश्चिम" in cleaned
    assert "बाजूची" in cleaned

    translated = TranslationService.translate_paragraph(corrupted_text, source_lang="Marathi")
    print(f"\nRAW: {corrupted_text}\nCLEAN: {cleaned}\nTRANS: {translated}")

    assert "zilla parishad" in translated.lower() or "district" in translated.lower()
