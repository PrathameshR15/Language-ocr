import os
import re
import uuid
import time
import json
import tempfile
import fitz  # PyMuPDF
from PIL import Image
from docx import Document as DocxDocument
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List

from config import settings
from backend.utils.logger import logger
from backend.utils.file_validator import sanitize_filename, validate_file_size, validate_file_extension, detect_corrupted_file
from backend.services.ocr_service import ocr_engine
from backend.services.language_detection_service import LanguageDetectionService
from backend.services.translation_service import translation_engine, INDIC_ADMIN_DICTIONARY, MARATHI_IDIOM_GLOSSARY
from backend.services.metadata_service import metadata_service
from backend.services.pdf_generation_service import pdf_generator
from backend.services.quality_validation_service import quality_validator
from backend.database.file_db import db_client

class DocumentParserService:
    """Master Pipeline Service executing Steps 1 to 13 of document translation workflow."""

    @staticmethod
    async def process_document(file_bytes: bytes, original_filename: str) -> Dict[str, Any]:
        start_time = time.time()
        doc_id = str(uuid.uuid4())[:8]
        clean_name = sanitize_filename(original_filename)

        # Clear in-memory translation cache to guarantee fresh translation pipeline execution
        translation_engine.clear_cache()

        # Step 2: Validate
        validate_file_size(file_bytes)
        ext = validate_file_extension(clean_name)


        paragraphs: List[Dict[str, Any]] = []
        overall_confidence = 0.90
        doc_type = "Image"

        # Use temporary directory for transient file reading during parsing (auto-deleted)
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_input_path = os.path.join(tmpdir, clean_name)
            with open(temp_input_path, "wb") as f:
                f.write(file_bytes)

            # Detect corruption
            detect_corrupted_file(temp_input_path, ext)

            # Step 3, 4, 5: Determine type & extract paragraphs using Hybrid Classifier
            if ext == "pdf":
                digital_paras, is_digital = ocr_engine.extract_digital_pdf_blocks(file_bytes)
                if is_digital:
                    doc_type = "Digital PDF"
                    paragraphs = digital_paras
                    overall_confidence = 1.00
                    logger.info(f"Doc {doc_id} classified as Digital PDF. Extracted {len(paragraphs)} digital blocks (OCR bypassed).")
                else:
                    doc_type = "Scanned PDF"
                    logger.info(f"Doc {doc_id} identified as Scanned PDF. Processing page images with OCR...")
                    pdf_doc = fitz.open(temp_input_path)
                    for page_num, page in enumerate(pdf_doc, start=1):
                        pix = page.get_pixmap(dpi=200)
                        img_path = os.path.join(tmpdir, f"temp_{doc_id}_p{page_num}.png")
                        pix.save(img_path)
                        
                        with Image.open(img_path) as pil_img:
                            page_paras, page_conf = ocr_engine.process_image(pil_img, page_num)
                            paragraphs.extend(page_paras)
                    pdf_doc.close()

            elif ext in ["png", "jpeg", "jpg", "tiff", "bmp"]:
                doc_type = "Image"
                logger.info(f"Doc {doc_id} identified as Image document.")
                with Image.open(temp_input_path) as pil_img:
                    paragraphs, overall_confidence = ocr_engine.process_image(pil_img, page_num=1)

            elif ext == "docx":
                doc_type = "Word Document"
                logger.info(f"Doc {doc_id} identified as Word DOCX.")
                docx_obj = DocxDocument(temp_input_path)
                para_idx = 1
                
                # 1. Extract paragraphs
                for p in docx_obj.paragraphs:
                    txt = p.text.strip()
                    if txt:
                        paragraphs.append({
                            "paragraph": para_idx,
                            "page": 1,
                            "text": txt,
                            "confidence": 0.99
                        })
                        para_idx += 1

                # 2. Extract tables as whole table grid blocks
                for table in docx_obj.tables:
                    raw_grid = []
                    for row in table.rows:
                        row_cells = []
                        for cell in row.cells:
                            c_text = cell.text.strip()
                            if not row_cells or c_text != row_cells[-1]:
                                row_cells.append(c_text)
                        if any(row_cells):
                            raw_grid.append(row_cells)
                    if raw_grid:
                        orig_md_lines = ["| " + " | ".join(raw_grid[0]) + " |", "| " + " | ".join(["---"] * len(raw_grid[0])) + " |"]
                        for r in raw_grid[1:]:
                            orig_md_lines.append("| " + " | ".join(r) + " |")
                        paragraphs.append({
                            "paragraph": para_idx,
                            "page": 1,
                            "text": "\n".join(orig_md_lines),
                            "confidence": 0.99,
                            "block_type": "table",
                            "table_grid": raw_grid
                        })
                        para_idx += 1

            elif ext == "txt":
                doc_type = "Text Document"
                logger.info(f"Doc {doc_id} identified as Text File.")
                try:
                    with open(temp_input_path, "r", encoding="utf-8", errors="ignore") as tf:
                        content = tf.read().strip()
                    if content:
                        blocks = re.split(r'\n\s*\n', content)
                        para_idx = 1
                        for block in blocks:
                            cleaned_block = " ".join([line.strip() for line in block.splitlines() if line.strip()])
                            if cleaned_block:
                                paragraphs.append({
                                    "paragraph": para_idx,
                                    "page": 1,
                                    "text": cleaned_block,
                                    "confidence": 1.00
                                })
                                para_idx += 1
                except Exception as e:
                    logger.error(f"Error reading TXT file {temp_input_path}: {e}")

        # Fallback if no text extracted
        if not paragraphs:
            paragraphs = [{
                "paragraph": 1,
                "page": 1,
                "text": "No readable text detected in document.",
                "confidence": 0.50
            }]

        # Step 8 & 9: Paragraph-wise Language Detection & Translation (Parallelized)
        from backend.services.translation_service import INDIC_ADMIN_DICTIONARY, normalize_indic_digits

        def _process_single_para(p):
            is_table_block = (p.get("block_type") == "table") or bool(p.get("table_grid"))
            if is_table_block and p.get("table_grid"):
                raw_grid = p.get("table_grid", [])
                trans_grid = []
                sample_text = ""
                for row in raw_grid:
                    trans_row = []
                    for cell in row:
                        c_str = str(cell or "").strip()
                        if c_str:
                            if not sample_text: sample_text = c_str
                            # 1. Fast optimization: If cell is numeric/currency/date string, normalize digits locally
                            if re.match(r'^[0-9\s,\.\-\+\(\)₹%\/०-९]+$', c_str):
                                t_cell = normalize_indic_digits(c_str)
                            # 2. Already English text
                            elif re.match(r'^[a-zA-Z0-9\s\.,\-\/\:\;\(\)₹%]+$', c_str):
                                t_cell = c_str
                            # 3. Exact administrative dictionary match
                            elif c_str in INDIC_ADMIN_DICTIONARY:
                                t_cell = INDIC_ADMIN_DICTIONARY[c_str]
                            # 4. Idiom / phrase glossary match
                            elif c_str in MARATHI_IDIOM_GLOSSARY:
                                t_cell = MARATHI_IDIOM_GLOSSARY[c_str]
                            else:
                                t_cell = translation_engine.translate_paragraph(c_str, "Marathi")
                            trans_row.append(t_cell)
                        else:
                            trans_row.append("")
                    trans_grid.append(trans_row)

                p_lang, lang_conf = LanguageDetectionService.detect_language_with_confidence(sample_text or "Table")
                p["language"] = p_lang
                p["language_confidence"] = lang_conf
                p["translated_table_grid"] = trans_grid
                p["block_type"] = "table"

                # Construct clean Markdown tables for original and translated content
                orig_md_lines = []
                if raw_grid:
                    orig_md_lines.append("| " + " | ".join(raw_grid[0]) + " |")
                    orig_md_lines.append("| " + " | ".join(["---"] * len(raw_grid[0])) + " |")
                    for r in raw_grid[1:]:
                        orig_md_lines.append("| " + " | ".join(r) + " |")
                orig_txt = "\n".join(orig_md_lines) if orig_md_lines else p.get("text", "")
                p["text"] = orig_txt

                trans_md_lines = []
                if trans_grid:
                    trans_md_lines.append("| " + " | ".join(trans_grid[0]) + " |")
                    trans_md_lines.append("| " + " | ".join(["---"] * len(trans_grid[0])) + " |")
                    for r in trans_grid[1:]:
                        trans_md_lines.append("| " + " | ".join(r) + " |")
                trans_txt = "\n".join(trans_md_lines) if trans_md_lines else "[TRANSLATED TABLE GRID]"
                p["translated_text"] = trans_txt
                p["translated_table_markdown"] = trans_txt

                return p, orig_txt, trans_txt, p_lang
            else:
                orig_txt = p.get("text", "")
                p_lang, lang_conf = LanguageDetectionService.detect_language_with_confidence(orig_txt)
                p["language"] = p_lang
                p["language_confidence"] = lang_conf

                # Fast bypass if paragraph is already pure English
                if p_lang == "English" and re.match(r'^[a-zA-Z0-9\s\.,\-\/\:\;\(\)₹%]+$', orig_txt):
                    trans_txt = orig_txt
                elif orig_txt in INDIC_ADMIN_DICTIONARY:
                    trans_txt = INDIC_ADMIN_DICTIONARY[orig_txt]
                elif orig_txt in MARATHI_IDIOM_GLOSSARY:
                    trans_txt = MARATHI_IDIOM_GLOSSARY[orig_txt]
                else:
                    trans_txt = translation_engine.translate_paragraph(orig_txt, p_lang)

                p["translated_text"] = trans_txt
                return p, orig_txt, trans_txt, p_lang

        detected_languages = []
        full_original_text_list = []
        full_translated_text_list = []

        if paragraphs:
            max_workers = min(10, max(1, len(paragraphs)))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                processed_items = list(executor.map(_process_single_para, paragraphs))

            for p, orig_txt, trans_txt, p_lang in processed_items:
                detected_languages.append(p_lang)
                full_original_text_list.append(orig_txt)
                full_translated_text_list.append(trans_txt)

        # Primary document language
        primary_lang = max(set(detected_languages), key=detected_languages.count) if detected_languages else "English"
        full_original_text = "\n\n".join(full_original_text_list)
        full_translated_text = "\n\n".join(full_translated_text_list)

        # Step 12: Generate Metadata
        metadata_json = metadata_service.extract_metadata(full_original_text + "\n" + full_translated_text, clean_name)
        metadata_json["document_type"] = doc_type

        # Smart filename resolution if uploaded filename is generic/random
        display_name = clean_name
        is_generic = (
            clean_name.lower().startswith(("government_document", "upload", "file", "tmp", "blob", "img_")) or
            re.match(r'^[a-f0-9\-_]{8,}$', clean_name.rsplit('.', 1)[0], re.IGNORECASE) or
            re.match(r'^\d+[\-_]', clean_name)
        )
        if is_generic:
            subj = metadata_json.get("subject", "")
            dept = metadata_json.get("department", "")
            doc_no = metadata_json.get("doc_number", "")
            
            if subj and subj != "N/A" and len(subj.strip()) > 3:
                clean_subj = sanitize_filename(subj)[:40]
                display_name = f"{clean_subj}.{ext}"
            elif dept and dept != "N/A" and doc_no and doc_no != "N/A":
                clean_dept = sanitize_filename(dept)[:25]
                clean_doc = sanitize_filename(doc_no)[:15]
                display_name = f"{clean_dept}_{clean_doc}.{ext}"
            elif clean_name.lower().startswith("government_document"):
                display_name = f"Document_{doc_id}.{ext}"

        processing_time = round(time.time() - start_time, 2)
        upload_time_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # Save original uploaded document file to UPLOAD_DIR for layout-preserved in-place redaction / PDF preview
        orig_file_path = os.path.join(settings.UPLOAD_DIR, f"{doc_id}_{clean_name}")
        try:
            with open(orig_file_path, "wb") as f:
                f.write(file_bytes)
        except Exception as e:
            logger.warning(f"Could not save original upload file to disk: {e}")
            orig_file_path = ""

        metadata_json["original_pdf_path"] = orig_file_path

        # Step 9 & 10: Run Quality Validation & Calculate Multi-Tier Confidence Scores
        qa_results = quality_validator.validate_translation(paragraphs, metadata_json)
        
        ocr_conf = round(qa_results.get("ocr_accuracy", 98.0) / 100.0, 2)
        trans_conf = round(qa_results.get("translation_accuracy", 98.0) / 100.0, 2)
        layout_conf = round(qa_results.get("layout_similarity", 97.0) / 100.0, 2)
        meta_conf = round(qa_results.get("metadata_accuracy", 100.0) / 100.0, 2)
        
        final_overall_conf = round(qa_results.get("overall_score", 98.0) / 100.0, 2)
        review_required = final_overall_conf < 0.95 or qa_results.get("review_required", False)

        metadata_json["confidence_metrics"] = {
            "ocr_confidence": ocr_conf,
            "translation_confidence": trans_conf,
            "layout_confidence": layout_conf,
            "metadata_confidence": meta_conf,
            "overall_confidence": final_overall_conf,
            "review_required": review_required,
            "warnings": qa_results["warnings"]
        }

        doc_record = {
            "id": doc_id,
            "filename": display_name,
            "original_extension": ext,

            "language": primary_lang,
            "translated_language": "English",
            "upload_time": upload_time_str,
            "processing_time": processing_time,
            "status": "completed",
            "confidence": qa_results.get("overall_score", 98.0) / 100.0,
            "quality_score": qa_results.get("overall_score", 98.0) / 100.0,
            "quality_report": qa_results,
            "review_required": review_required,
            "original_pdf_path": orig_file_path,
            "translated_pdf_path": "",
            "translated_same_format_path": "",
            "metadata_json": metadata_json
        }

        # Step 13: Store record & extracted texts in FileDB
        await db_client.save_document(doc_record)
        await db_client.save_extracted_texts(doc_id, paragraphs)

        doc_record["paragraphs"] = paragraphs
        logger.info(f"Completed processing document {doc_id} ({clean_name}) in {processing_time}s")
        return doc_record

document_parser = DocumentParserService()
