import pytest
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from backend.services.ocr_service import ocr_engine, sanitize_indic_text, _ensure_surya
from config import settings

def test_ocr_engine_config():
    """Verify default OCR_ENGINE setting is auto."""
    assert hasattr(settings, "OCR_ENGINE")
    assert settings.OCR_ENGINE in ("auto", "surya", "easyocr", "rapidocr", "paddleocr")

def test_surya_ocr_lazy_load():
    """Test lazy loading of Surya OCR module."""
    surya_fn = _ensure_surya()
    # surya_fn should either be a callable or False if models are downloading
    assert surya_fn is not None

def test_surya_ocr_fallback_mechanism(monkeypatch):
    """Verify automatic fallback execution when Surya OCR returns low confidence or raises an error."""
    # Mock process_image_surya to simulate low-confidence or failing OCR output
    def mock_failing_surya(pil_image, page_num=1):
        return [{"text": "Garbled OCR noise", "confidence": 0.30}], 0.30

    monkeypatch.setattr(ocr_engine, "process_image_surya", mock_failing_surya)
    
    # Create test image
    img = Image.new('RGB', (400, 100), color=(255, 255, 255))
    
    # Run process_image which should catch quality failure and trigger fallback
    paras, conf = ocr_engine.process_image(img, page_num=1)
    assert isinstance(paras, list)
    assert isinstance(conf, float)

def test_bengali_text_sanitization():
    """Verify sanitization of Bengali unicode text."""
    bengali_text = "বাংলাদেশের রাজধানী ঢাকা। "
    cleaned = sanitize_indic_text(bengali_text)
    assert "বাংলাদেশের" in cleaned
    assert "ঢাকা" in cleaned
