import pytest
from backend.services.llm_enhancement_service import llm_service
from config import settings

def test_llm_ocr_correction_config():
    """Verify ENABLE_LLM_OCR_CORRECTION configuration setting."""
    assert hasattr(settings, "ENABLE_LLM_OCR_CORRECTION")
    assert isinstance(settings.ENABLE_LLM_OCR_CORRECTION, bool)

def test_correct_ocr_paragraphs_with_llm_mock(monkeypatch):
    """Test LLM post-OCR correction formatting and batch mapping."""
    paragraphs = [
        {"paragraph": 1, "page": 1, "text": "ऊजार्ट बचति के साथ नबार्टधि सुविधिा उपलब्ध कराना।", "confidence": 0.85},
        {"paragraph": 2, "page": 1, "text": "ज्येष्ठ व गुणवंत कलावंतांचा गौरव तळेघर येथे केला।", "confidence": 0.90}
    ]

    # Mock _call_llm_raw to simulate LLM JSON response repairing OCR typos
    def mock_llm_raw(prompt, timeout=8.0):
        return '''[
            {"id": 0, "corrected_text": "ऊर्जा बचत के साथ नाबार्ड सुविधा उपलब्ध कराना।"},
            {"id": 1, "corrected_text": "ज्येष्ठ व गुणवंत कलावंतांचा गौरव तळेघर येथे केला।"}
        ]'''

    monkeypatch.setattr(llm_service, "_call_llm_raw", mock_llm_raw)
    monkeypatch.setattr(llm_service, "is_available", lambda: True)

    corrected = llm_service.correct_ocr_paragraphs_with_llm(paragraphs)
    assert len(corrected) == 2
    assert "ऊर्जा" in corrected[0]["text"]
    assert "नाबार्ड" in corrected[0]["text"]
    assert "तळेघर" in corrected[1]["text"]
    assert corrected[0]["ocr_raw_text"] == "ऊजार्ट बचति के साथ नबार्टधि सुविधिा उपलब्ध कराना।"
