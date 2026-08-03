import pytest
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from backend.services.table_transformer_service import table_transformer_service


def create_sample_table_image():
    """Generates a synthetic document image containing a clean grid table."""
    img = Image.new("RGB", (600, 400), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Draw table border and lines
    draw.rectangle([50, 50, 550, 250], outline=(0, 0, 0), width=2)
    # Horizontal line
    draw.line([50, 100, 550, 100], fill=(0, 0, 0), width=2)
    draw.line([50, 150, 550, 150], fill=(0, 0, 0), width=1)
    draw.line([50, 200, 550, 200], fill=(0, 0, 0), width=1)

    # Vertical line
    draw.line([300, 50, 300, 250], fill=(0, 0, 0), width=2)

    # Add text inside table
    draw.text((70, 70), "Header Item", fill=(0, 0, 0))
    draw.text((320, 70), "Header Value", fill=(0, 0, 0))

    draw.text((70, 120), "Row 1", fill=(0, 0, 0))
    draw.text((320, 120), "Value 1", fill=(0, 0, 0))

    draw.text((70, 170), "Row 2", fill=(0, 0, 0))
    draw.text((320, 170), "Value 2", fill=(0, 0, 0))

    return img


def test_table_transformer_imports():
    """Verifies that Table Transformer service is available."""
    assert table_transformer_service is not None


def test_table_transformer_reconstruction():
    """Tests table detection and reconstruction pipeline with mock OCR blocks."""
    img = create_sample_table_image()

    ocr_blocks = [
        {"text": "Header Item", "bbox": [70, 70, 170, 90]},
        {"text": "Header Value", "bbox": [320, 70, 420, 90]},
        {"text": "Row 1", "bbox": [70, 120, 130, 140]},
        {"text": "Value 1", "bbox": [320, 120, 380, 140]},
        {"text": "Row 2", "bbox": [70, 170, 130, 190]},
        {"text": "Value 2", "bbox": [320, 170, 380, 190]},
    ]

    # Test reconstruction function
    results = table_transformer_service.reconstruct_table(img, ocr_blocks)
    
    # Check that reconstruction ran without error and returned result list
    assert isinstance(results, list)
    if results:
        res = results[0]
        assert "grid" in res
        assert "markdown" in res
        assert "html" in res
        assert isinstance(res["grid"], list)
