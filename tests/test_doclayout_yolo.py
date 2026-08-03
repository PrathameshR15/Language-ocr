import pytest
from backend.services.layout_parser_service import LayoutParserService

def test_doclayout_yolo_classifications():
    """Verify LayoutParserService handles block classification and visual layout detection."""
    text = "सार्वजनिक सूचना - भूसंपादन निवाडा"
    bbox = [100.0, 50.0, 500.0, 80.0]
    block_type, props = LayoutParserService.classify_block_type(text, bbox, page_width=595.0, page_height=842.0)
    
    assert block_type == "title"
    assert props["bold"] is True
    assert props["align"] == "center"

def test_doclayout_yolo_elements_parser():
    """Verify parse_layout_elements calculates bounding box metrics."""
    sample_blocks = [{
        "text": "कार्यालय उपजिल्हाधिकारी पुणे",
        "bbox": [300.0, 20.0, 550.0, 45.0],
        "page": 1,
        "confidence": 0.98
    }]
    
    layout_results = LayoutParserService.parse_layout_elements(sample_blocks, page_width=595.0, page_height=842.0)
    assert len(layout_results) == 1
    assert layout_results[0]["block_type"] == "office_address"
    assert layout_results[0]["width"] == 250.0
    assert layout_results[0]["height"] == 25.0
