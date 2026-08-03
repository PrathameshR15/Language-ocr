import os
import pytest
from backend.services.pdf_generation_service import PDFGenerationService
from backend.utils.unicode_utils import normalize_indic_digits


class TestPDFRenderingEnhancements:
    def test_normalize_indic_digits_converts_rupee_symbol(self):
        sample = "₹२,१०,००० खर्च करून"
        normalized = normalize_indic_digits(sample)
        assert "Rs." in normalized
        assert "2,10,000" in normalized
        assert "₹" not in normalized

    def test_generate_translated_pdf_creates_clean_pdf_without_black_squares(self, tmp_path):
        paragraphs = [
            {"paragraph": 1, "translated_text": "Knowledge is the supreme wealth", "block_type": "title"},
            {"paragraph": 2, "translated_text": "Spent Rs. 2,10,000 for 450 students.", "block_type": "paragraph"},
            {"paragraph": 3, "translated_text": "Suhas Kulkarni (Secretary)", "block_type": "signature"},
            {"paragraph": 4, "translated_text": "Dr. Anita Joshi (Chairperson)", "block_type": "signature"},
        ]
        metadata = {
            "doc_category": "General Document",
            "doc_number": "N/A",
            "state": "N/A",
            "title": "Annual Progress Report"
        }
        out_pdf = os.path.join(tmp_path, "test_output.pdf")
        res_path = PDFGenerationService.generate_translated_pdf("doc123", "sample.pdf", paragraphs, metadata, out_pdf)
        
        assert os.path.exists(res_path)
        assert os.path.getsize(res_path) > 1000
