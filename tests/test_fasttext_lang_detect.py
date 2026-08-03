import pytest
from backend.services.language_detection_service import LanguageDetectionService

def test_language_detection_indic_marathi():
    """Test Devanagari Marathi script keyword detection (Hybrid Rule)."""
    text = "हा वार्षिक ग्राम विकास प्रगती अहवाल आहे. जिल्हा पुणे."
    lang, conf = LanguageDetectionService.detect_language_with_confidence(text)
    assert lang == "Marathi"
    assert conf >= 0.90

def test_language_detection_indic_hindi():
    """Test Devanagari Hindi script keyword detection (Hybrid Rule)."""
    text = "यह उत्तर प्रदेश सरकार का आधिकारिक सूचना पत्र है।"
    lang, conf = LanguageDetectionService.detect_language_with_confidence(text)
    assert lang == "Hindi"
    assert conf >= 0.90

def test_language_detection_indic_gujarati():
    """Test Gujarati Unicode script detection."""
    text = "આ વાર્ષિક વિકાસ અહેવાલ છે."
    lang, conf = LanguageDetectionService.detect_language_with_confidence(text)
    assert lang == "Gujarati"
    assert conf >= 0.85

def test_language_detection_spanish():
    """Test Spanish text detection."""
    text = "Este es un informe oficial del gobierno de España sobre el desarrollo."
    lang, conf = LanguageDetectionService.detect_language_with_confidence(text)
    assert lang in ["Spanish", "Spanish (Spain)"]
    assert conf >= 0.50

def test_language_detection_french():
    """Test French text detection."""
    text = "Ceci est un rapport officiel du gouvernement français concernant le développement."
    lang, conf = LanguageDetectionService.detect_language_with_confidence(text)
    assert lang == "French"
    assert conf >= 0.50
