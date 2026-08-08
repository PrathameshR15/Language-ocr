import pytest
from backend.services.translation_service import TranslationService
from backend.services.language_detection_service import LanguageDetectionService

def test_language_detection_multilingual():
    """Verify language detection across various Indian and global scripts."""
    cases = [
        ("ગુજરાતી સરકાર યોજના", "Gujarati"),
        ("தமிழ்நாடு அரசு அறிவிப்பு", "Tamil"),
        ("తెలుగు భాషా దినోత్సవం", "Telugu"),
        ("ಕನ್ನಡ ರಾಜ್ಯೋತ್ಸವ", "Kannada"),
        ("മലയാളം വാര്‍ത്തകള്‍", "Malayalam"),
        ("ਪੰਜਾਬੀ ਖ਼ਬਰਾਂ", "Punjabi"),
        ("পশ্চিমবঙ্গ সরকার", "Bengali"),
        ("Bonjour tout le monde", "French"),
        ("Hola cómo estás", "Spanish"),
        ("Guten Tag mein Freund", "German")
    ]
    for text, expected_lang in cases:
        detected = LanguageDetectionService.detect_language(text)
        assert detected.lower() == expected_lang.lower(), f"Expected {expected_lang}, got {detected} for '{text}'"

def test_multilingual_translation_execution():
    """Verify translation execution across diverse languages into English."""
    sample_phrases = [
        ("ગુજરાત પંચાયત પરિપત્ર", "Gujarati"),
        ("தமிழ்நாடு அரசு சேவைகள்", "Tamil"),
        ("తెలుగు ప్రభుత్వ నిర్ణయం", "Telugu"),
        ("കർഷക ക്ഷേമ പദ്ധതി", "Malayalam"),
        ("Le gouvernement de la France", "French")
    ]
    for text, lang in sample_phrases:
        translated = TranslationService.translate_paragraph(text, source_lang=lang)
        assert isinstance(translated, str)
        assert len(translated.strip()) > 0
