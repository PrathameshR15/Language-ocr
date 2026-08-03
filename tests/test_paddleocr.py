import pytest
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from backend.services.ocr_service import OCRService

def test_paddleocr_import_and_init():
    """Test if PaddleOCR can be imported or initialized in OCRService."""
    ocr = OCRService()
    # Check if get_paddleocr_engine returns an engine or None gracefully without crashing
    paddle_engine = ocr.get_paddleocr_engine()
    # Should not raise exception
    assert paddle_engine is None or hasattr(paddle_engine, 'ocr')

def test_paddleocr_image_processing():
    """Test OCR processing on a dummy image using OCRService."""
    # Create simple RGB image with text box
    img = Image.new("RGB", (400, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 35), "GOVERNMENT REPORT", fill=(0, 0, 0))

    ocr = OCRService()
    paras, conf = ocr.process_image(img, page_num=1)
    
    assert isinstance(paras, list)
    assert isinstance(conf, float)
