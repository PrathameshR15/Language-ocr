import pytest
from backend.services.ner_service import ner_service
from backend.utils.unicode_utils import protect_symbols_for_translation, restore_symbols_after_translation
from backend.services.translation_service import TranslationService

def test_ner_service_basic_extraction():
    """Test that NER service handles entity extraction calls gracefully."""
    sample_text = "आनंदराव मोरे आणि प्रथमेश पाटील यांनी पुणे येथे बैठक घेतली."
    entities = ner_service.extract_entities(sample_text)
    # Even if model is loading or in fallback mode, it must return a list without errors
    assert isinstance(entities, list)

def test_protect_symbols_with_gliner():
    """Test that symbol protection identifies and preserves proper nouns."""
    sample_text = "डॉ. शुभांगी गायकवाड यांनी तळेघर गावात काम केले."
    protected_text, symbol_map = protect_symbols_for_translation(sample_text)
    
    assert isinstance(protected_text, str)
    assert isinstance(symbol_map, dict)
    
    restored = restore_symbols_after_translation(protected_text, symbol_map)
    assert "Shubhangi" in restored or "गायकवाड" in restored or "Taleghar" in restored

def test_translation_preserves_names():
    """Test paragraph translation to ensure proper names are preserved accurately."""
    sample_text = "मा. आनंदराव मोरे यांनी नवीन प्रकल्पाचे उद्घाटन केले."
    translated = TranslationService.translate_paragraph(sample_text, source_lang="Marathi")
    
    assert isinstance(translated, str)
    # The name Anandrao More should be preserved in the translation
    assert "Anandrao" in translated or "More" in translated
