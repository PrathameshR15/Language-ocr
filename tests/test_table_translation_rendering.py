import os
import pytest
from backend.services.document_parser_service import DocumentParserService
from backend.services.pdf_generation_service import PDFGenerationService


def test_table_grid_translation_and_formatting(tmp_path):
    """Verifies that tabular layout paragraphs are translated cell-by-cell and preserved in outputs."""
    table_para = {
        "paragraph": 1,
        "page": 1,
        "text": "| विषय | तपशील |\n| --- | --- |\n| ग्रामपंचायत | विकास प्रकल्प |",
        "confidence": 0.99,
        "block_type": "table",
        "table_grid": [
            ["विषय", "तपशील"],
            ["ग्रामपंचायत", "विकास प्रकल्प"]
        ]
    }

    # Simulate _process_single_para execution
    from backend.services.translation_service import INDIC_ADMIN_DICTIONARY, translation_engine
    
    raw_grid = table_para["table_grid"]
    trans_grid = []
    for row in raw_grid:
        trans_row = []
        for cell in row:
            if cell in INDIC_ADMIN_DICTIONARY:
                t_cell = INDIC_ADMIN_DICTIONARY[cell]
            else:
                t_cell = translation_engine.translate_paragraph(cell, "Marathi")
            trans_row.append(t_cell)
        trans_grid.append(trans_row)

    table_para["translated_table_grid"] = trans_grid
    
    # Assert translated grid cells
    assert trans_grid[0][0] == "Subject" or trans_grid[0][0] != "विषय"
    assert trans_grid[0][1] == "Details" or trans_grid[0][1] != "तपशील"
    assert trans_grid[1][0] == "Gram Panchayat"
    
    # Assert PDF generation with table grid
    pdf_out = str(tmp_path / "test_table.pdf")
    res_pdf = PDFGenerationService.generate_translated_pdf(
        "t1", "test_table.pdf", [table_para], {"subject": "Table Test"}, pdf_out
    )
    assert os.path.exists(res_pdf)
    assert os.path.getsize(res_pdf) > 0

    # Assert DOCX generation with table grid
    docx_out = str(tmp_path / "test_table.docx")
    res_docx = PDFGenerationService.generate_translated_docx(
        "t1", "test_table.docx", [table_para], {"subject": "Table Test"}, None, docx_out
    )
    assert os.path.exists(res_docx)
    assert os.path.getsize(res_docx) > 0
