import pytest
from backend.services.translation_service import TranslationService, clean_ocr_text

def test_bengali_ocr_text_cleaning():
    """Verify that Bengali OCR font noise and broken vowel signs are cleaned properly."""
    raw_ocr = "তাহলে আপনি যদি বাংলোয় চানি, তব একই সংক্ষিপ্ত প্রতבדিনিটি নিচ দিওয়া হলো:"
    cleaned = clean_ocr_text(raw_ocr)
    assert "বাংলা" in cleaned
    assert "প্রতিবেদন" in cleaned

def test_bengali_translation_quality_end_to_end():
    """Verify high-accuracy translation of Bengali PDF document blocks."""
    test_cases = [
        ("তাহলে আপনি যদি বাংলায় চান, তবে একই সংক্ষিপ্ত প্রতিবেদনটি নিচে দেওয়া হলো:", ["Bengali", "report"]),
        ("গ্রাম উন্নয়ন কাজ - সংক্ষিপ্ত প্রতিবেদন", ["Village Development Work", "Brief Report"]),
        ("পঞ্চায়েত সমিতি খেড় / আম্বেগাঁও সারসংক্ষেপ", ["Panchayat Samiti", "Ambegaon"]),
        ("শ্রী রমেশ গাদেকর", ["Ramesh Gadekar"]),
        ("শ্রীমতী রেখা ওয়োদেকর", ["Rekha"]),
        ("(সহ-সচিব)", ["Secretary"]),
        ("বিদ্যালয় মেরামত, রাস্তা ও নর্দমা নির্মাণ", ["School", "repair", "road"])
    ]

    for source_text, expected_phrases in test_cases:
        translated = TranslationService.translate_paragraph(source_text, source_lang="Bengali")
        print(f"\nSRC: {source_text}\nTRANS: {translated}")

        for phrase in expected_phrases:
            assert phrase.lower() in translated.lower(), f"Expected '{phrase}' in translation of '{source_text}', got '{translated}'"
        
        # Ensure no bungalow or pain hallucinations
        assert "bungalow" not in translated.lower(), f"Found 'bungalow' hallucination in '{translated}'"
        assert "abbreviated pain" not in translated.lower(), f"Found 'abbreviated pain' hallucination in '{translated}'"
