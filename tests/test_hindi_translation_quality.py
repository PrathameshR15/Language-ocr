import pytest
from backend.services.translation_service import TranslationService

def test_hindi_infrastructure_and_civic_phrases():
    """Verify clean translation of Hindi civic, infrastructure, and administrative phrases."""
    test_cases = [
        ("पीने के पानी की नई पाइपलाइन", ["Drinking Water", "Pipeline"]),
        ("पेयजल आपूर्ति एवं जल जीवन मिशन", ["Drinking Water", "Supply", "Jal Jeevan Mission"]),
        ("सड़क व नाली निर्माण कार्य", ["Road", "drain", "Construction"]),
        ("ग्राम पंचायत भवन निर्माण", ["Gram Panchayat", "building"]),
        ("प्राथमिक स्वास्थ्य केंद्र", ["Primary Health Center"]),
        ("Pine Ke Pani Ki Nai Pipeline", ["Drinking Water", "Pipeline"])
    ]

    for source_text, expected_phrases in test_cases:
        translated = TranslationService.translate_paragraph(source_text, source_lang="Hindi")
        print(f"\nSRC: {source_text}\nTRANS: {translated}")

        for phrase in expected_phrases:
            assert phrase.lower() in translated.lower(), f"Expected '{phrase}' in translation of '{source_text}', got '{translated}'"
