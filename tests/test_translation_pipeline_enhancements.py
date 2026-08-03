import pytest
from backend.services.translation_service import (
    TranslationService,
    is_corrupted_romanized_marathi,
    recover_corrupted_romanized_marathi,
    MARATHI_IDIOM_GLOSSARY,
)
from backend.utils.unicode_utils import (
    protect_symbols_for_translation,
    restore_symbols_after_translation,
    clean_unrestored_placeholders,
)
from backend.services.ocr_service import ocr_engine


class TestCorruptedRomanizedMarathiRecovery:
    """Requirement 1 & 2: Detect & recover corrupted Romanized Marathi before sending to IndicTrans2."""

    def test_detects_corrupted_romanized_marathi(self):
        corrupted_sample = "Adh3pan vi smaarterv classroom prashikshan"
        assert is_corrupted_romanized_marathi(corrupted_sample, "Marathi") is True

    def test_recovers_corrupted_romanized_marathi_to_devanagari(self):
        corrupted_sample = "Adh3pan vi smaarterv classroom prashikshan"
        recovered = recover_corrupted_romanized_marathi(corrupted_sample)
        # Should contain Devanagari script for Adhyapan, vi, prashikshan
        assert "अध्यापन" in recovered
        assert "प्रशिक्षण" in recovered
        # Should preserve 'classroom' or 'Smart'
        assert "classroom" in recovered.lower() or "स्मार्ट" in recovered

    def test_translation_pipeline_handles_corrupted_ocr_input(self):
        corrupted_sample = "Adh3pan vi smaarterv classroom prashikshan"
        translation = TranslationService.translate_paragraph(corrupted_sample, "Marathi")
        assert len(translation) > 0
        # Check that translation produces meaningful English terms
        assert any(kw in translation.lower() for kw in ["teaching", "smart", "classroom", "training", "education"])


class TestMixedLanguagePreservation:
    """Requirement 3: Preserve English terms like 'Smart Classroom', 'Smart Board', 'Students'."""

    def test_preserves_smart_classroom_terms(self):
        text = "शाळेत Smart Classroom आणि Smart Board ची सोय उपलब्ध आहे."
        protected, sym_map = protect_symbols_for_translation(text)
        assert len(sym_map) >= 1
        
        restored = restore_symbols_after_translation(protected, sym_map)
        assert "Smart Classroom" in restored or "Smart Board" in restored


class TestMarathiIdiomContextualTranslation:
    """Requirement 5: Detect Marathi idioms and contextual verbal phrases by meaning."""

    def test_hatbhar_lavne_idiom(self):
        res1 = TranslationService.translate_paragraph("विद्यार्थ्यांनी विकास कामात हातभार लावला.", "Marathi")
        assert "contributed" in res1.lower() or "support" in res1.lower() or "participated" in res1.lower()
        # Ensure it is NOT translated literally as 'put hand'
        assert "put their hand" not in res1.lower() and "hand on" not in res1.lower()


class TestPlaceholderAndSymbolCleanup:
    """Requirement 6: Zero leftover [SYM_x] or black square artifacts in final document."""

    def test_cleans_leftover_placeholders(self):
        raw_output = "The Government Order [[SYM_0]] was approved [SYM_1] with ■ black square."
        cleaned = clean_unrestored_placeholders(raw_output)
        assert "[[SYM_0]]" not in cleaned
        assert "[SYM_1]" not in cleaned
        assert "■" not in cleaned
        assert "Government Order" in cleaned


class TestOCRValidationAndFragmentMerging:
    """Requirement 4 & 7: OCR validation, retry preprocessing, and sentence fragment merging."""

    def test_ocr_validation_detects_garbled_output(self):
        garbled_paras = [{"text": "ROTORORE RAaRAOURORE"}]
        is_valid, reason = ocr_engine.validate_ocr_quality(garbled_paras, 0.50)
        assert is_valid is False
        assert "garbled" in reason.lower() or "confidence" in reason.lower()

    def test_ocr_merges_sentence_fragments(self):
        fragments = [
            {"paragraph": 1, "text": "महाराष्ट्र शासनाच्या शिक्षण विभागाने", "is_list": False},
            {"paragraph": 2, "text": "नवीन उपक्रम सुरू केला आहे.", "is_list": False}
        ]
        merged = ocr_engine.merge_ocr_line_fragments(fragments)
        assert len(merged) == 1
        assert merged[0]["text"] == "महाराष्ट्र शासनाच्या शिक्षण विभागाने नवीन उपक्रम सुरू केला आहे."
