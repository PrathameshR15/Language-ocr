import pytest
from backend.services.ocr_service import ocr_engine

def test_corrupted_digital_pdf_validation_failure():
    """Verify that selectable text containing box drawing glyphs or garbled noise is rejected."""
    corrupted_paras = [
        {"paragraph": 1, "page": 1, "text": "■Gabor and ■Kan=tea use 7Banyamu=ly", "confidence": 1.00},
        {"paragraph": 2, "page": 1, "text": "7Bashmukt ■Jabai Upa=y Shaksab", "confidence": 1.00}
    ]

    # Validate OCR quality on corrupted digital text should fail (return False)
    is_valid, reason = ocr_engine.validate_ocr_quality(corrupted_paras, avg_conf=1.00)
    assert is_valid is False
    assert "missing glyph boxes" in reason or "garbled ASCII noise" in reason

def test_clean_digital_pdf_validation_success():
    """Verify that clean selectable text is successfully accepted without triggering fallback."""
    clean_paras = [
        {"paragraph": 1, "page": 1, "text": "Rural Organic Agriculture and Soil Conservation Project Report", "confidence": 1.00},
        {"paragraph": 2, "page": 1, "text": "Farmers get fair price and workers are healthy.", "confidence": 1.00}
    ]

    is_valid, reason = ocr_engine.validate_ocr_quality(clean_paras, avg_conf=1.00)
    assert is_valid is True
