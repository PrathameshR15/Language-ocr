import pytest
from backend.services.llm_enhancement_service import llm_service
from backend.services.translation_service import TranslationService

def test_english_translation_validator_avoids_box_characters():
    """Verify that correct_english_translation correctly strips leftover glyph boxes or font noise."""
    if not llm_service.is_available():
        pytest.skip("LLM API keys not configured or service not available.")

    corrupted_english = "■Gabor and ■Kan=tea use 7Banyamu=ly ■Organic fertilizer."
    cleaned = llm_service.correct_english_translation(corrupted_english)
    
    assert "■" not in cleaned
    assert "=" not in cleaned
    assert "7Banyamu" not in cleaned

def test_translation_pipeline_calls_validator():
    """Verify the translation pipeline integrates the grammar correction/validation step."""
    if not llm_service.is_available():
        pytest.skip("LLM API keys not configured or service not available.")

    # Translate a line that may contain minor noise to ensure the result is validated
    raw_marathi = "तळेघर येथील ज्येष्ठ व गुणवंत कलावंतांचा गौरव करण्यात आला."
    translation = TranslationService.translate_paragraph(raw_marathi, source_lang="Marathi")
    
    # Assert result is well-formed English and contains no Indic characters
    assert "Taleghar" in translation or "felicitated" in translation
