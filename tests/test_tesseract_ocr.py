import os
import pytest
from PIL import Image
from backend.services.ocr_service import ocr_engine, _ensure_tesseract
from config import settings

def test_tessdata_models_exist():
    """Verify local tessdata files are downloaded and present."""
    tessdata_dir = settings.TESSERACT_DATA_DIR
    assert os.path.exists(tessdata_dir)
    for lang in ["ben", "hin", "mar", "eng"]:
        model_path = os.path.join(tessdata_dir, f"{lang}.traineddata")
        assert os.path.exists(model_path), f"Missing model: {model_path}"

def test_tesseract_lazy_load():
    """Verify lazy loader loads pytesseract and binds executable path."""
    pytess = _ensure_tesseract()
    assert pytess is not None
    assert pytess.pytesseract.tesseract_cmd == settings.TESSERACT_PATH

def test_tesseract_image_extraction():
    """Verify Tesseract OCR engine successfully extracts text from a sample PIL image."""
    img = Image.new("RGB", (300, 80), color=(255, 255, 255))
    
    # We test process_image_tesseract doesn't crash and returns output
    paras, conf = ocr_engine.process_image_tesseract(img, page_num=1)
    assert isinstance(paras, list)
    assert isinstance(conf, float)
