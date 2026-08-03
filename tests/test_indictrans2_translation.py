import pytest
from backend.services.translation_service import TranslationService, INDICTRANS_LANG_MAP

def test_indictrans2_language_mappings():
    """Verify all major Indic languages are mapped to IndicTrans2 language codes."""
    assert INDICTRANS_LANG_MAP.get("marathi") == "mar_Deva"
    assert INDICTRANS_LANG_MAP.get("hindi") == "hin_Deva"
    assert INDICTRANS_LANG_MAP.get("gujarati") == "guj_Gujr"
    assert INDICTRANS_LANG_MAP.get("tamil") == "tam_Taml"
    assert INDICTRANS_LANG_MAP.get("telugu") == "tel_Telu"

def test_translation_pipeline_marathi():
    """Test paragraph translation pipeline on Marathi administrative text."""
    marathi_text = "वार्षिक ग्राम विकास प्रगती अहवाल"
    translated = TranslationService.translate_paragraph(marathi_text, "Marathi")
    upper = translated.upper()
    assert "ANNUAL" in upper or "VILLAGE" in upper or "DEVELOPMENT" in upper or "PROGRESS" in upper
    assert len(translated) > 0

def test_translation_pipeline_hindi():
    """Test paragraph translation pipeline on Hindi public notice text."""
    hindi_text = "सार्वजनिक सूचना चुनाव प्रक्रिया"
    translated = TranslationService.translate_paragraph(hindi_text, "Hindi")
    upper = translated.upper()
    assert "ELECTION" in upper or "NOTICE" in upper or "PUBLIC" in upper or "PROCESS" in upper
    assert len(translated) > 0

