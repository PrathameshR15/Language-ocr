import re
import numpy as np
# pyrefly: ignore [missing-import]
from PIL import Image
from typing import List, Dict, Any, Tuple
from backend.services.preprocessing_service import ImagePreprocessingService
from backend.services.layout_parser_service import layout_parser
from backend.utils.logger import logger

# All heavy OCR engines are lazily imported only when first used to keep startup fast
fitz = None
easyocr = None
PaddleOCR = None
RapidOCR = None

def _ensure_fitz():
    global fitz
    if fitz is None:
        try:
            # pyrefly: ignore [missing-import]
            import fitz as _fitz
            fitz = _fitz
        except ImportError:
            pass
    return fitz

def _ensure_easyocr():
    global easyocr
    if easyocr is None:
        try:
            # pyrefly: ignore [missing-import]
            import easyocr as _easyocr
            easyocr = _easyocr
        except ImportError:
            pass
    return easyocr

def _ensure_paddleocr():
    global PaddleOCR
    if PaddleOCR is None:
        try:
            # pyrefly: ignore [missing-import]
            from paddleocr import PaddleOCR as _PaddleOCR
            PaddleOCR = _PaddleOCR
        except ImportError:
            pass
    return PaddleOCR

# Tesseract OCR lazy loading handles
pytesseract = None

def _ensure_tesseract():
    global pytesseract
    if pytesseract is None:
        try:
            # pyrefly: ignore [missing-import]
            import pytesseract as _pytesseract
            from config import settings
            _pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH
            pytesseract = _pytesseract
            logger.info("pytesseract engine initialized successfully.")
        except ImportError:
            pass
    return pytesseract

# Surya OCR lazy loading handles
surya_rec_predictor = None
surya_initialized = None

def _ensure_surya():
    global surya_rec_predictor, surya_initialized
    if surya_initialized is None:
        try:
            # pyrefly: ignore [missing-import]
            from surya.recognition import RecognitionPredictor
            logger.info("Initializing Surya OCR RecognitionPredictor...")
            surya_rec_predictor = RecognitionPredictor()
            surya_initialized = True
            logger.info("Surya OCR RecognitionPredictor loaded successfully.")
        except Exception as e:
            logger.warning(f"Could not load Surya OCR engine/models: {e}")
            surya_initialized = False
    return surya_initialized

def _ensure_rapidocr():
    global RapidOCR
    if RapidOCR is None:
        try:
            # pyrefly: ignore [missing-import]
            from rapidocr_onnxruntime import RapidOCR as _RapidOCR
            RapidOCR = _RapidOCR
        except ImportError:
            pass
    return RapidOCR


def sanitize_indic_text(text: str) -> str:
    """Sanitizes text extracted from PDFs with custom font encoding or corrupted glyph cmap markers."""
    if not text:
        return ""
    # Remove non-standard out-of-range glyph noise inserted by custom PDF font cmaps
    cleaned = re.sub(r'[\u0530-\u058F\u05C0-\u05FF\u1B00-\u1B7F]', '', text)
    cleaned = re.sub(r'[^\S\n]+', ' ', cleaned).strip()
    return cleaned

class OCRService:
    """Multilingual OCR Engine utilizing EasyOCR, PaddleOCR, & RapidOCR with OpenCV preprocessing."""

    def __init__(self):
        # Engines are lazy-loaded on first use to keep server startup fast
        self.engine = None
        self._easyocr_reader = None
        self._paddleocr_engine = None
        logger.info("OCRService initialized (engines will lazy-load on first use).")

    def _get_rapidocr(self):
        """Lazy-initializes RapidOCR engine on first call."""
        if self.engine is None:
            _RapidOCR = _ensure_rapidocr()
            if _RapidOCR is not None:
                try:
                    self.engine = _RapidOCR()
                    logger.info("RapidOCR engine initialized successfully.")
                except Exception as e:
                    logger.warning(f"Could not initialize RapidOCR engine: {e}")
                    self.engine = None
        return self.engine


    def get_paddleocr_engine(self, lang: str = "ch"):
        """Lazy-loads PaddleOCR engine with specified language support (default: Multilingual/Devanagari)."""
        _PaddleOCR = _ensure_paddleocr()
        if self._paddleocr_engine is None and _PaddleOCR is not None:
            for l in [lang, "ch"]:
                try:
                    logger.info(f"Initializing PaddleOCR engine (lang='{l}')...")
                    self._paddleocr_engine = _PaddleOCR(lang=l, enable_mkldnn=False)
                    logger.info(f"PaddleOCR engine loaded successfully ({l}).")
                    break
                except Exception as e:
                    logger.warning(f"PaddleOCR init failed for {l}: {e}")
                    self._paddleocr_engine = None

        return self._paddleocr_engine






    def get_easyocr_reader(self):
        """Lazy-loads EasyOCR reader with Devanagari (Hindi, Marathi, Bengali) & English models with verbose=False for Windows compatibility."""
        _easyocr = _ensure_easyocr()
        if self._easyocr_reader is None and _easyocr is not None:
            for langs in [['bn', 'hi', 'mr', 'en'], ['bn', 'en'], ['hi', 'mr', 'en'], ['mr', 'en'], ['hi', 'en']]:
                try:
                    logger.info(f"Initializing EasyOCR reader for Indic models {langs}...")
                    self._easyocr_reader = _easyocr.Reader(langs, gpu=False, verbose=False)
                    logger.info(f"EasyOCR Indic reader loaded successfully ({langs}).")
                    break
                except Exception as e:
                    logger.warning(f"EasyOCR reader init failed for {langs}: {e}")
                    self._easyocr_reader = None
        return self._easyocr_reader

    def is_garbled_ascii(self, paragraphs: List[Dict[str, Any]]) -> bool:
        """Checks if OCR text output consists of garbled ASCII noise (e.g. random non-character gibberish)."""
        if not paragraphs:
            return True
        total_text = " ".join([p.get("text", "") for p in paragraphs])
        if not total_text.strip():
            return True
        
        # Check if text contains Indic unicode (Devanagari, Tamil, Telugu, etc.)
        indic_char_count = len(re.findall(r'[\u0900-\u0DFF]', total_text))
        if indic_char_count >= 2:
            return False  # Valid Indic text found
            
        # Check for garbled uppercase/lowercase patterns typical of broken OCR
        garbled_patterns = [
            r'[:\)\(\-_\/\\]{4,}',
            r'\b[A-Z]{4,}\d+[A-Z]+\b',
            r'\b(?:ROTORORE|RAaRAOURORE|OBRORBRO|INGIUATATEERROREF)\b',
        ]
        
        for pat in garbled_patterns:
            if re.search(pat, total_text, re.IGNORECASE):
                return True
                
        # If no Indic characters were detected, check ratio of unprintable/corrupted noise words
        words = [w.strip() for w in total_text.split() if len(w.strip()) > 2]
        if words and indic_char_count == 0:
            # Allow standard punctuation, currency, numbers, and symbols
            noisy_words = [w for w in words if re.search(r'[^a-zA-Z0-9\s\u0900-\u097F\.\,\-\/\:\;\(\)₹%\@\#\$\&\*\+=\[\]\{\}"\'\|]', w)]
            if len(noisy_words) / float(len(words)) > 0.40:
                return True

        return False

    def validate_ocr_quality(self, paragraphs: List[Dict[str, Any]], avg_conf: float) -> Tuple[bool, str]:
        """Validate OCR output quality before passing text to translation pipeline.
        Returns (is_valid, reason_message).
        """
        if not paragraphs:
            return False, "Empty OCR paragraph output"

        total_text = " ".join([p.get("text", "") for p in paragraphs]).strip()
        if not total_text or len(total_text) < 3:
            return False, "Trivial text output"

        if avg_conf < 0.75:
            return False, f"Low OCR confidence ({avg_conf} < 0.75)"

        if any(c in total_text for c in ['■', '□', '\ufffd']):
            return False, "OCR text contains missing glyph boxes"

        # Check for split matra digit corruptions or box characters inside Indic text
        words = total_text.split()
        if words:
            corrupt_count = 0
            for w in words:
                # e.g., starts with 7, 3, 4 followed by Indic char (like 7বদু্যৎ), or contains ǂ, ǃ, or =
                if re.search(r'^[734\u096D\u096A][\u0900-\u0DFF]', w) or any(c in w for c in ['ǂ', 'ǃ', '=']):
                    corrupt_count += 1
            if corrupt_count / len(words) > 0.05: # If more than 5% of words are corrupted
                return False, "OCR text contains split glyph symbols (CMap corruption)"

        if self.is_garbled_ascii(paragraphs):
            return False, "OCR text contains garbled ASCII noise"

        return True, "Valid OCR output"

    @staticmethod
    def detect_table_grid_from_paragraphs(paragraphs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detects tabular sequence of OCR lines and converts them into structured table paragraph blocks."""
        if not paragraphs or len(paragraphs) < 2:
            return paragraphs

        result_paras = []
        table_candidates = []

        def flush_table_candidates():
            nonlocal table_candidates, result_paras
            if not table_candidates:
                return
            if len(table_candidates) >= 2:
                grid = []
                for tp in table_candidates:
                    t_str = tp.get("text", "").strip()
                    if "|" in t_str:
                        cells = [c.strip() for c in t_str.split("|") if c.strip()]
                    else:
                        cells = [c.strip() for c in re.split(r'\s{2,}', t_str) if c.strip()]
                    if cells:
                        grid.append(cells)
                if grid and len(grid[0]) >= 2:
                    max_cols = max(len(r) for r in grid)
                    norm_grid = [r + [""] * (max_cols - len(r)) for r in grid]
                    result_paras.append({
                        "paragraph": len(result_paras) + 1,
                        "page": table_candidates[0].get("page", 1),
                        "text": table_candidates[0].get("text", ""),
                        "block_type": "table",
                        "table_grid": norm_grid,
                        "confidence": 0.99
                    })
                else:
                    result_paras.extend(table_candidates)
            else:
                result_paras.extend(table_candidates)
            table_candidates = []

        for p in paragraphs:
            txt = p.get("text", "").strip()
            is_tbl_row = False
            if p.get("block_type") == "table" or p.get("table_grid"):
                is_tbl_row = True
            elif "|" in txt and len(txt.split("|")) >= 3:
                is_tbl_row = True
            elif re.search(r'^\s*[0-9\u0966-\u096F]+[\.\s]', txt) and len(re.split(r'\s{2,}', txt)) >= 3:
                is_tbl_row = True
            elif re.search(r'^\s*(?:क्र[\.\s]|उपक्रमाचे|कालावधी|खर्च|एकूण|लाभार्थी|Sr\.|No\.)', txt) and len(re.split(r'\s{2,}|\|', txt)) >= 3:
                is_tbl_row = True

            if is_tbl_row:
                table_candidates.append(p)
            else:
                flush_table_candidates()
                result_paras.append(p)

        flush_table_candidates()
        return result_paras

    @classmethod
    def merge_ocr_line_fragments(cls, paragraphs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merges adjacent line fragments into complete sentences and reconstructs tabular grids."""
        if not paragraphs:
            return paragraphs

        # Sort paragraphs top-to-bottom by page number and top Y coordinate (bbox[1])
        paragraphs.sort(key=lambda p: (
            p.get("page", 1),
            p.get("bbox", [0, 0, 0, 0])[1] if p.get("bbox") else 0,
            p.get("bbox", [0, 0, 0, 0])[0] if p.get("bbox") else 0
        ))

        # First pass: Auto-detect table grid lines
        paragraphs = cls.detect_table_grid_from_paragraphs(paragraphs)

        merged = []
        para_idx = 1

        STRUCTURAL_TYPES = {"title", "heading", "section_heading", "table", "signature", "office_address", "header", "footer"}

        for p in paragraphs:
            txt = p.get("text", "").strip()
            if not txt:
                continue

            b_type = p.get("block_type", "paragraph")

            # Always preserve structural blocks (tables, titles, headings, signatures, list items) as independent units
            if b_type in STRUCTURAL_TYPES or p.get("table_grid") or p.get("is_list"):
                p_copy = dict(p)
                p_copy["paragraph"] = para_idx
                merged.append(p_copy)
                para_idx += 1
                continue

            if merged:
                prev = merged[-1]
                prev_text = prev["text"].strip()
                prev_b_type = prev.get("block_type", "paragraph")

                # Only merge body prose fragments into previous body block if previous block is not a structural boundary
                # and does not end with sentence termination (Danda '।', '.', '?', '!')
                if (prev_b_type not in STRUCTURAL_TYPES 
                        and not prev.get("table_grid") 
                        and not prev.get("is_list")
                        and not re.search(r'[\u0964\u0965.\!\?\|]\s*$', prev_text)):
                    
                    merged[-1]["text"] = f"{prev_text} {txt}".strip()
                    if "confidence" in p and "confidence" in merged[-1]:
                        merged[-1]["confidence"] = round((merged[-1]["confidence"] + p["confidence"]) / 2.0, 2)
                    
                    # Update bounding box to encompass merged fragment
                    if prev.get("bbox") and p.get("bbox"):
                        b1 = prev["bbox"]
                        b2 = p["bbox"]
                        merged[-1]["bbox"] = [
                            min(b1[0], b2[0]),
                            min(b1[1], b2[1]),
                            max(b1[2], b2[2]),
                            max(b1[3], b2[3])
                        ]
                    continue

            p_copy = dict(p)
            p_copy["paragraph"] = para_idx
            merged.append(p_copy)
            para_idx += 1

        return merged

    @staticmethod


    def extract_digital_pdf_blocks(pdf_bytes_or_path: Any) -> Tuple[List[Dict[str, Any]], bool]:
        """Inspects PDF pages using PyMuPDF (fitz). If pages contain selectable text, extracts digital blocks with font size, bold, alignment, and bbox without running OCR."""
        fitz = _ensure_fitz()
        if fitz is None:
            return [], False

        try:
            if isinstance(pdf_bytes_or_path, bytes):
                doc = fitz.open(stream=pdf_bytes_or_path, filetype="pdf")
            else:
                doc = fitz.open(pdf_bytes_or_path)

            paragraphs = []
            has_digital_text = False
            para_idx = 1

            for page_num, page in enumerate(doc, 1):

                page_w = page.rect.width
                page_h = page.rect.height
                page_paras = []

                # 1. Detect Tables using PyMuPDF TableFinder API
                table_bboxes = []
                try:
                    tabs = page.find_tables()
                    if tabs and tabs.tables:
                        for tab in tabs.tables:
                            t_bbox = list(tab.bbox)
                            raw_grid = tab.extract()
                            clean_grid = []
                            cell_bboxes = []
                            if raw_grid:
                                for r_idx, row in enumerate(raw_grid):
                                    clean_row = [sanitize_indic_text(str(cell or "")) for cell in row]
                                    if any(clean_row):
                                        clean_grid.append(clean_row)
                                        row_bboxes = []
                                        if hasattr(tab, "cells") and tab.cells:
                                            for c_idx in range(len(row)):
                                                cell_idx = c_idx * tab.row_count + r_idx
                                                cell_bbox = tab.cells[cell_idx] if cell_idx < len(tab.cells) else None
                                                row_bboxes.append(list(cell_bbox) if cell_bbox else None)
                                        else:
                                            row_bboxes = [None] * len(row)
                                        cell_bboxes.append(row_bboxes)

                            if clean_grid:
                                has_digital_text = True
                                table_bboxes.append(t_bbox)
                                page_paras.append({
                                    "paragraph": para_idx,
                                    "page": page_num,
                                    "text": "[TABLE GRID]",
                                    "table_grid": clean_grid,
                                    "table_cell_bboxes": cell_bboxes,
                                    "confidence": 1.00,
                                    "bbox": t_bbox,
                                    "block_type": "table",
                                    "alignment": "center",
                                    "bold": False,
                                    "font_size": 10,
                                    "page_width": page_w,
                                    "page_height": page_h,
                                    "source": "digital"
                                })
                                para_idx += 1
                except Exception as e:
                    logger.debug(f"PyMuPDF table detection skipped on page {page_num}: {e}")

                # 2. Extract Non-Table Text Blocks
                page_dict = page.get_text("dict")
                blocks = page_dict.get("blocks", [])

                for b in blocks:
                    if b.get("type") == 0 and b.get("lines"): # Text block
                        for line in b["lines"]:
                            bbox = list(line.get("bbox", [0, 0, 0, 0]))

                            # Skip line if it falls inside any detected table rectangle
                            inside_table = False
                            for tb in table_bboxes:
                                if bbox[0] >= (tb[0] - 5) and bbox[1] >= (tb[1] - 5) and bbox[2] <= (tb[2] + 5) and bbox[3] <= (tb[3] + 5):
                                    inside_table = True
                                    break
                            if inside_table:
                                continue

                            line_text = ""
                            font_sizes = []
                            is_bold = False

                            for span in line.get("spans", []):
                                stext = sanitize_indic_text(span.get("text", ""))
                                if stext:
                                    line_text += stext + " "
                                    font_sizes.append(span.get("size", 10))
                                    fname = span.get("font", "").lower()
                                    flags = span.get("flags", 0)
                                    if "bold" in fname or "black" in fname or (flags & 2):
                                        is_bold = True

                            clean_t = line_text.strip()
                            if clean_t and len(clean_t) >= 2:
                                has_digital_text = True
                                avg_fs = sum(font_sizes) / len(font_sizes) if font_sizes else 10.0

                                b_type, props = layout_parser.classify_block_type(clean_t, bbox, page_w, page_h)
                                if is_bold:
                                    props["bold"] = True

                                page_paras.append({
                                    "paragraph": para_idx,
                                    "page": page_num,
                                    "text": clean_t,
                                    "confidence": 1.00,
                                    "bbox": bbox,
                                    "block_type": b_type,
                                    "alignment": props["align"],
                                    "bold": props["bold"],
                                    "font_size": round(avg_fs, 1),
                                    "is_list": props["is_list"],
                                    "list_prefix": props["list_prefix"],
                                    "page_width": page_w,
                                    "page_height": page_h,
                                    "source": "digital"
                                })
                # 3. Sort page blocks (tables and text blocks) by top-to-bottom Y coordinate reading order
                page_paras.sort(key=lambda p: (p.get("bbox", [0, 0, 0, 0])[1], p.get("bbox", [0, 0, 0, 0])[0]))

                # Reassign paragraph sequence indices in exact natural top-to-bottom reading order
                for p in page_paras:
                    p["paragraph"] = para_idx
                    para_idx += 1

                paragraphs.extend(page_paras)

            doc.close()
            if has_digital_text and paragraphs:
                logger.info(f"[HYBRID CLASSIFIER] Classified PDF as DIGITAL. Extracted {len(paragraphs)} selectable text blocks directly via PyMuPDF (OCR bypassed).")
                return paragraphs, True
            else:
                return [], False
        except Exception as e:
            logger.warning(f"Digital PDF block extraction skipped: {e}")
            return [], False

    def process_image_easyocr(self, cv_img: np.ndarray, page_num: int = 1) -> Tuple[List[Dict[str, Any]], float]:
        """Performs OCR extraction using EasyOCR for Indic scripts."""
        reader = self.get_easyocr_reader()
        if not reader:
            return [], 0.0

        try:
            results = reader.readtext(cv_img)
            if not results:
                return [], 0.0

            page_h, page_w = cv_img.shape[:2]

            # Sort lines top-to-bottom by top y coordinate then x
            sorted_results = sorted(
                results,
                key=lambda item: (item[0][0][1], item[0][0][0])
            )

            paragraphs = []

            confidences = []
            current_para_texts = []
            current_confidences = []
            current_boxes = []
            last_box = None
            para_idx = 1

            for box, text, score in sorted_results:
                clean_t = sanitize_indic_text(text)
                if not clean_t or len(clean_t) < 2:
                    continue

                min_x = min(pt[0] for pt in box)
                min_y = min(pt[1] for pt in box)
                max_y = max(pt[1] for pt in box)
                line_h = max_y - min_y
                score_val = float(score) if score else 0.85

                split_block = False
                if last_box:
                    last_min_x = min(pt[0] for pt in last_box)
                    last_max_y = max(pt[1] for pt in last_box)
                    gap = min_y - last_max_y
                    if gap > max(12.0, line_h * 1.15):
                        split_block = True
                    elif abs(min_x - last_min_x) > 40:
                        split_block = True
                    elif re.match(r'^(?:[\(（]?[0-9\u0966-\u096F]{1,3}[\)\）\.]|[\(（]?[a-zA-Z\u0900-\u097F][\)\）\.]|[०-९\d]+\))\s*', clean_t.strip()):
                        split_block = True
                    elif any(clean_t.strip().startswith(k) or clean_t.strip() == k for k in ["वाचा :-", "वाचा:", "विषय :-", "विषय:", "प्रस्तावना :-", "अंतिम निवाडा", "तपशील :-", "आदेश :-"]):
                        split_block = True

                if split_block and current_para_texts:
                    full_text = " ".join(current_para_texts)
                    avg_conf = sum(current_confidences) / len(current_confidences)
                    b_min_x = min(b[0][0] for b in current_boxes)
                    b_min_y = min(b[0][1] for b in current_boxes)
                    b_max_x = max(b[2][0] for b in current_boxes)
                    b_max_y = max(b[2][1] for b in current_boxes)
                    bbox = [float(b_min_x), float(b_min_y), float(b_max_x), float(b_max_y)]

                    b_type, props = layout_parser.classify_block_type(full_text, bbox, page_w, page_h)

                    paragraphs.append({
                        "paragraph": para_idx,
                        "page": page_num,
                        "text": full_text,
                        "confidence": round(avg_conf, 2),
                        "bbox": bbox,
                        "block_type": b_type,
                        "alignment": props["align"],
                        "bold": props["bold"],
                        "font_size": props["font_size"],
                        "is_list": props["is_list"],
                        "list_prefix": props["list_prefix"],
                        "page_width": page_w,
                        "page_height": page_h
                    })
                    para_idx += 1
                    current_para_texts = []
                    current_confidences = []
                    current_boxes = []

                current_para_texts.append(clean_t)
                current_confidences.append(score_val)
                current_boxes.append(box)
                confidences.append(score_val)
                last_box = box

            if current_para_texts:
                full_text = " ".join(current_para_texts)
                avg_conf = sum(current_confidences) / len(current_confidences)
                min_x = min(b[0][0] for b in current_boxes)
                min_y = min(b[0][1] for b in current_boxes)
                max_x = max(b[2][0] for b in current_boxes)
                max_y = max(b[2][1] for b in current_boxes)
                bbox = [float(min_x), float(min_y), float(max_x), float(max_y)]

                b_type, props = layout_parser.classify_block_type(full_text, bbox, page_w, page_h)

                paragraphs.append({
                    "paragraph": para_idx,
                    "page": page_num,
                    "text": full_text,
                    "confidence": round(avg_conf, 2),
                    "bbox": bbox,
                    "block_type": b_type,
                    "alignment": props["align"],
                    "bold": props["bold"],
                    "font_size": props["font_size"],
                    "is_list": props["is_list"],
                    "list_prefix": props["list_prefix"],
                    "page_width": page_w,
                    "page_height": page_h
                })

            avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.88
            logger.info(f"EasyOCR page {page_num} extracted {len(paragraphs)} paragraphs (Avg Conf: {avg_conf})")
            return paragraphs, avg_conf

        except Exception as e:
            logger.error(f"EasyOCR processing failed on page {page_num}: {e}")
            return [], 0.0

    def process_image_paddleocr(self, cv_img: np.ndarray, page_num: int = 1) -> Tuple[List[Dict[str, Any]], float]:
        """Performs OCR extraction using PaddleOCR pretrained model."""
        engine = self.get_paddleocr_engine()
        if not engine:
            return [], 0.0

        try:
            results = engine.ocr(cv_img)
            if not results or not results[0]:
                return [], 0.0

            page_h, page_w = cv_img.shape[:2]
            paragraphs = []
            confidences = []
            para_idx = 1

            for item in results[0]:
                if isinstance(item, dict):
                    text = item.get("rec_text", "")
                    score = item.get("rec_score", 0.90)
                    box = item.get("rec_polys", item.get("dt_polys", []))
                elif isinstance(item, (list, tuple)) and len(item) == 2:
                    box, (text, score) = item
                else:
                    continue

                clean_t = sanitize_indic_text(text)
                if not clean_t or len(clean_t) < 2:
                    continue


                min_x = min(pt[0] for pt in box)
                min_y = min(pt[1] for pt in box)
                max_x = max(pt[0] for pt in box)
                max_y = max(pt[1] for pt in box)
                bbox = [float(min_x), float(min_y), float(max_x), float(max_y)]
                score_val = float(score) if score else 0.90

                b_type, props = layout_parser.classify_block_type(clean_t, bbox, page_w, page_h)

                paragraphs.append({
                    "paragraph": para_idx,
                    "page": page_num,
                    "text": clean_t,
                    "confidence": round(score_val, 2),
                    "bbox": bbox,
                    "block_type": b_type,
                    "alignment": props["align"],
                    "bold": props["bold"],
                    "font_size": props["font_size"],
                    "is_list": props["is_list"],
                    "list_prefix": props["list_prefix"],
                    "page_width": page_w,
                    "page_height": page_h,
                    "source": "paddleocr"
                })
                confidences.append(score_val)
                para_idx += 1

            avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.90
            logger.info(f"PaddleOCR page {page_num} extracted {len(paragraphs)} paragraphs (Avg Conf: {avg_conf})")
            return paragraphs, avg_conf

        except Exception as e:
            logger.error(f"PaddleOCR processing failed on page {page_num}: {e}")
            return [], 0.0

    def process_image_surya(self, pil_image: Image.Image, page_num: int = 1, langs: List[str] = None) -> Tuple[List[Dict[str, Any]], float]:
        """Performs OCR extraction using Surya OCR model."""
        is_ready = _ensure_surya()
        if not is_ready:
            return [], 0.0

        try:
            w, h = pil_image.size
            lang_list = [langs] if langs else [["bn", "hi", "mr", "en"]]

            surya_det_predictor = None
            predictions = surya_rec_predictor(
                images=[pil_image],
                langs=lang_list,
                det_predictor=surya_det_predictor
            )

            if not predictions or not hasattr(predictions[0], "text_lines") or not predictions[0].text_lines:
                return [], 0.0

            page_result = predictions[0]
            page_w, page_h = w, h
            paragraphs = []
            confidences = []
            para_idx = 1

            # Sort lines top-to-bottom
            lines = sorted(page_result.text_lines, key=lambda l: (getattr(l, "bbox", [0,0,0,0])[1], getattr(l, "bbox", [0,0,0,0])[0]))

            current_para_texts = []
            current_confidences = []
            current_boxes = []
            last_bbox = None

            for line in lines:
                text = sanitize_indic_text(getattr(line, "text", ""))
                if not text or len(text) < 2:
                    continue

                bbox = list(getattr(line, "bbox", [0, 0, 0, 0]))
                score = getattr(line, "confidence", None)
                if score is None:
                    score = getattr(line, "score", 0.90)
                score_val = float(score) if score else 0.90

                split_block = False
                if last_bbox:
                    gap = bbox[1] - last_bbox[3]
                    line_h = bbox[3] - bbox[1]
                    if gap > max(12.0, line_h * 1.15) or abs(bbox[0] - last_bbox[0]) > 40:
                        split_block = True

                if split_block and current_para_texts:
                    full_text = " ".join(current_para_texts)
                    avg_conf = sum(current_confidences) / len(current_confidences)
                    b_min_x = min(b[0] for b in current_boxes)
                    b_min_y = min(b[1] for b in current_boxes)
                    b_max_x = max(b[2] for b in current_boxes)
                    b_max_y = max(b[3] for b in current_boxes)
                    comb_bbox = [float(b_min_x), float(b_min_y), float(b_max_x), float(b_max_y)]

                    b_type, props = layout_parser.classify_block_type(full_text, comb_bbox, page_w, page_h)

                    paragraphs.append({
                        "paragraph": para_idx,
                        "page": page_num,
                        "text": full_text,
                        "confidence": round(avg_conf, 2),
                        "bbox": comb_bbox,
                        "block_type": b_type,
                        "alignment": props["align"],
                        "bold": props["bold"],
                        "font_size": props["font_size"],
                        "is_list": props["is_list"],
                        "list_prefix": props["list_prefix"],
                        "page_width": page_w,
                        "page_height": page_h,
                        "source": "surya"
                    })
                    para_idx += 1
                    current_para_texts = []
                    current_confidences = []
                    current_boxes = []

                current_para_texts.append(text)
                current_confidences.append(score_val)
                current_boxes.append(bbox)
                confidences.append(score_val)
                last_bbox = bbox

            if current_para_texts:
                full_text = " ".join(current_para_texts)
                avg_conf = sum(current_confidences) / len(current_confidences)
                b_min_x = min(b[0] for b in current_boxes)
                b_min_y = min(b[1] for b in current_boxes)
                b_max_x = max(b[2] for b in current_boxes)
                b_max_y = max(b[3] for b in current_boxes)
                comb_bbox = [float(b_min_x), float(b_min_y), float(b_max_x), float(b_max_y)]

                b_type, props = layout_parser.classify_block_type(full_text, comb_bbox, page_w, page_h)

                paragraphs.append({
                    "paragraph": para_idx,
                    "page": page_num,
                    "text": full_text,
                    "confidence": round(avg_conf, 2),
                    "bbox": comb_bbox,
                    "block_type": b_type,
                    "alignment": props["align"],
                    "bold": props["bold"],
                    "font_size": props["font_size"],
                    "is_list": props["is_list"],
                    "list_prefix": props["list_prefix"],
                    "page_width": page_w,
                    "page_height": page_h,
                    "source": "surya"
                })

            avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.90
            logger.info(f"Surya OCR page {page_num} extracted {len(paragraphs)} paragraphs (Avg Conf: {avg_conf})")
            return paragraphs, avg_conf

        except Exception as e:
            logger.error(f"Surya OCR processing failed on page {page_num}: {e}")
            return [], 0.0

    def detect_languages_for_tesseract(self, pil_image: Image.Image, tessdata_dir: str) -> str:
        """Detects primary language script in image using a fast pre-pass to prevent multi-script confusion."""
        pytess = _ensure_tesseract()
        if not pytess:
            return "eng"
        try:
            import os
            # Set TESSDATA_PREFIX environment variable so Tesseract can resolve paths containing spaces on Windows
            abs_tessdata_dir = os.path.abspath(tessdata_dir)
            os.environ["TESSDATA_PREFIX"] = abs_tessdata_dir
            w, h = pil_image.size
            small_img = pil_image.resize((w // 2, h // 2))
            custom_config = '--psm 3'
            sample_text = pytess.image_to_string(small_img, lang="ben+hin+mar+eng", config=custom_config)
            
            bengali_chars = len(re.findall(r'[\u0980-\u09FF]', sample_text))
            devanagari_chars = len(re.findall(r'[\u0900-\u097F]', sample_text))
            
            if bengali_chars > 5 and bengali_chars > devanagari_chars:
                logger.info(f"[TESSERACT LANG DETECT] Detected primary script: BENGALI ({bengali_chars} chars)")
                return "ben+eng"
            elif devanagari_chars > 5:
                logger.info(f"[TESSERACT LANG DETECT] Detected primary script: DEVANAGARI ({devanagari_chars} chars)")
                return "mar+hin+eng"
        except Exception as e:
            logger.warning(f"Tesseract language pre-detection failed: {e}")
        return "ben+hin+mar+eng"

    def process_image_tesseract(self, pil_image: Image.Image, page_num: int = 1) -> Tuple[List[Dict[str, Any]], float]:
        """Performs OCR extraction using Tesseract OCR with local traineddata models."""
        pytess = _ensure_tesseract()
        if not pytess:
            return [], 0.0

        try:
            import os
            from config import settings
            w, h = pil_image.size

            # Set TESSDATA_PREFIX environment variable so Tesseract can resolve paths containing spaces on Windows
            abs_tessdata_dir = os.path.abspath(settings.TESSERACT_DATA_DIR)
            os.environ["TESSDATA_PREFIX"] = abs_tessdata_dir
            
            # Detect primary language script to improve accuracy
            target_langs = self.detect_languages_for_tesseract(pil_image, abs_tessdata_dir)

            # Request word-level bounding boxes and confidence scores
            data = pytess.image_to_data(
                pil_image,
                lang=target_langs,
                output_type=pytess.Output.DICT
            )

            paragraphs = []
            confidences = []

            # Group words by block_num and par_num
            groups = {}
            n_items = len(data.get("text", []))

            for i in range(n_items):
                text = str(data["text"][i]).strip()
                conf = float(data["conf"][i]) if "conf" in data else -1.0

                # Skip layout background or unconfident empty spaces
                if not text or conf == -1.0 or conf < 10.0:
                    continue

                block_num = data["block_num"][i]
                par_num = data["par_num"][i]
                key = (block_num, par_num)

                if key not in groups:
                    groups[key] = {
                        "words": [],
                        "confidences": [],
                        "boxes": []
                    }

                left = float(data["left"][i])
                top = float(data["top"][i])
                width = float(data["width"][i])
                height = float(data["height"][i])
                box = [left, top, left + width, top + height]

                groups[key]["words"].append(text)
                groups[key]["confidences"].append(conf / 100.0) # Convert 0-100 to 0.0-1.0
                groups[key]["boxes"].append(box)
                confidences.append(conf / 100.0)

            para_idx = 1
            for (block_num, par_num), grp in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1])):
                full_text = " ".join(grp["words"])
                clean_t = sanitize_indic_text(full_text)
                if not clean_t or len(clean_t) < 2:
                    continue

                avg_conf = sum(grp["confidences"]) / len(grp["confidences"])

                b_min_x = min(box[0] for box in grp["boxes"])
                b_min_y = min(box[1] for box in grp["boxes"])
                b_max_x = max(box[2] for box in grp["boxes"])
                b_max_y = max(box[3] for box in grp["boxes"])
                comb_bbox = [b_min_x, b_min_y, b_max_x, b_max_y]

                b_type, props = layout_parser.classify_block_type(clean_t, comb_bbox, w, h)

                paragraphs.append({
                    "paragraph": para_idx,
                    "page": page_num,
                    "text": clean_t,
                    "confidence": round(avg_conf, 2),
                    "bbox": comb_bbox,
                    "block_type": b_type,
                    "alignment": props["align"],
                    "bold": props["bold"],
                    "font_size": props["font_size"],
                    "is_list": props["is_list"],
                    "list_prefix": props["list_prefix"],
                    "page_width": w,
                    "page_height": h,
                    "source": "tesseract"
                })
                para_idx += 1

            avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.90
            logger.info(f"Tesseract OCR page {page_num} extracted {len(paragraphs)} paragraphs (Avg Conf: {avg_conf})")
            return paragraphs, avg_conf

        except Exception as e:
            logger.error(f"Tesseract OCR processing failed on page {page_num}: {e}")
            return [], 0.0

    def process_image(self, pil_image: Image.Image, page_num: int = 1) -> Tuple[List[Dict[str, Any]], float]:
        """Runs image preprocessing, performs OCR extraction using primary configured engine (Tesseract/Surya/Auto) with automatic fallback."""
        from config import settings
        engine_mode = getattr(settings, "OCR_ENGINE", "auto").lower()

        w, h = pil_image.size
        if max(w, h) > 1600:
            scale = 1600.0 / float(max(w, h))
            new_w, new_h = int(w * scale), int(h * scale)
            pil_image = pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)

        cv_img = ImagePreprocessingService.pil_to_cv2(pil_image)

        # 1. Primary Engine: Tesseract OCR (when OCR_ENGINE is 'auto' or 'tesseract')
        if engine_mode in ("auto", "tesseract"):
            try:
                tess_paras, tess_conf = self.process_image_tesseract(pil_image, page_num)
                is_valid, reason = self.validate_ocr_quality(tess_paras, tess_conf)
                if is_valid:
                    merged_paras = self.merge_ocr_line_fragments(tess_paras)
                    logger.info(f"[OCR ENGINE - TESSERACT] Extracted {len(merged_paras)} blocks for page {page_num} (Conf: {tess_conf})")
                    return merged_paras, tess_conf
                else:
                    logger.warning(f"[OCR FALLBACK TRIGGERED] Tesseract OCR output validation failed: {reason}. Falling back...")
            except Exception as e:
                logger.warning(f"[OCR FALLBACK TRIGGERED] Tesseract OCR error: {e}. Falling back...")

        # 2. Secondary Engine: Surya OCR (when OCR_ENGINE is 'surya')
        if engine_mode == "surya":
            try:
                surya_paras, surya_conf = self.process_image_surya(pil_image, page_num)
                is_valid, reason = self.validate_ocr_quality(surya_paras, surya_conf)
                if is_valid:
                    merged_paras = self.merge_ocr_line_fragments(surya_paras)
                    logger.info(f"[OCR ENGINE - SURYA] Extracted {len(merged_paras)} blocks for page {page_num} (Conf: {surya_conf})")
                    return merged_paras, surya_conf
                else:
                    logger.warning(f"[OCR FALLBACK TRIGGERED] Surya OCR output validation failed: {reason}. Falling back...")
            except Exception as e:
                logger.warning(f"[OCR FALLBACK TRIGGERED] Surya OCR error: {e}. Falling back...")

        # 3. Secondary Engine: RapidOCR
        paragraphs = []
        confidences = []
        _engine = self._get_rapidocr()
        if _engine:
            try:
                results, _ = _engine(cv_img)
                if not results:
                    # Fallback to grayscale if raw color image returned no text boxes
                    # pyrefly: ignore [missing-import]
                    import cv2
                    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY) if len(cv_img.shape) == 3 else cv_img
                    results, _ = _engine(gray)

                if results:
                    sorted_boxes = sorted(
                        results,
                        key=lambda item: (round(item[0][0][1] / 15.0) * 15.0, item[0][0][0])
                    )
                    
                    current_para_texts = []
                    current_confidences = []
                    last_y = None
                    para_idx = 1

                    for box, text, score in sorted_boxes:
                        clean_t = sanitize_indic_text(text)
                        if not clean_t:
                            continue
                        
                        top_y = box[0][1]
                        score_val = float(score) if score else 0.90
                        
                        if last_y is not None and abs(top_y - last_y) > 35:
                            if current_para_texts:
                                full_text = " ".join(current_para_texts)
                                avg_conf = sum(current_confidences) / len(current_confidences)
                                p_obj = {
                                    "paragraph": para_idx,
                                    "page": page_num,
                                    "text": full_text,
                                    "confidence": round(avg_conf, 2),
                                    "box": box
                                }
                                paragraphs.append(p_obj)
                                para_idx += 1
                                current_para_texts = []
                                current_confidences = []

                        current_para_texts.append(clean_t)
                        current_confidences.append(score_val)
                        confidences.append(score_val)
                        last_y = top_y

                    if current_para_texts:
                        full_text = " ".join(current_para_texts)
                        avg_conf = sum(current_confidences) / len(current_confidences)
                        p_obj = {
                            "paragraph": para_idx,
                            "page": page_num,
                            "text": full_text,
                            "confidence": round(avg_conf, 2)
                        }
                        paragraphs.append(p_obj)

                avg_doc_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.92
                merged_paras = self.merge_ocr_line_fragments(paragraphs)
                return merged_paras, avg_doc_conf

            except Exception as e:
                logger.error(f"RapidOCR processing failed on page {page_num}: {e}")

        # 3. Fallback: EasyOCR (if RapidOCR fails or throws exception)
        _easyocr = _ensure_easyocr()
        if _easyocr is not None:
            try:
                easy_paras, easy_conf = self.process_image_easyocr(cv_img, page_num)
                if easy_paras:
                    merged_paras = self.merge_ocr_line_fragments(easy_paras)
                    return merged_paras, easy_conf
            except Exception as e:
                logger.warning(f"EasyOCR fallback processing failed: {e}")

        # 4. Fallback: PaddleOCR (if previous fallbacks failed)
        _PaddleOCR = _ensure_paddleocr()
        if _PaddleOCR is not None:
            paddle_paras, paddle_conf = self.process_image_paddleocr(cv_img, page_num)
            if paddle_paras:
                merged_paras = self.merge_ocr_line_fragments(paddle_paras)
                return merged_paras, paddle_conf

        avg_document_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.92
        merged_paras = self.merge_ocr_line_fragments(paragraphs)
        
        # 5. Final Fallback: OpenAI Vision (if all OCR engines returned corrupted/invalid text)
        if merged_paras:
            is_valid, _ = self.validate_ocr_quality(merged_paras, avg_document_confidence)
            if not is_valid:
                from backend.services.openai_vision_service import openai_vision_service
                if openai_vision_service.is_available():
                    logger.warning(f"[OCR FALLBACK TRIGGERED] All OCR engines returned corrupted output for page {page_num}. Using OpenAI Vision...")
                    import tempfile, os
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
                        pil_image.save(tmp_file.name)
                        tmp_path = tmp_file.name
                    try:
                        ai_text = openai_vision_service.extract_text_from_image(tmp_path, lang_hint="Marathi")
                        os.unlink(tmp_path)
                        if ai_text:
                            ai_paras = []
                            # Split by double newline to preserve paragraph blocks, or single newline
                            blocks = re.split(r'\n\s*\n', ai_text) if '\n\n' in ai_text else ai_text.split('\n')
                            para_idx = 1
                            for block in blocks:
                                clean_t = block.strip()
                                if clean_t:
                                    ai_paras.append({
                                        "paragraph": para_idx,
                                        "page": page_num,
                                        "text": clean_t,
                                        "confidence": 0.99,
                                        "source": "openai_vision",
                                        "block_type": "paragraph"
                                    })
                                    para_idx += 1
                            if ai_paras:
                                logger.info(f"[OPENAI VISION] Successfully extracted {len(ai_paras)} paragraphs for page {page_num}.")
                                return ai_paras, 0.99
                    except Exception as e:
                        logger.error(f"OpenAI Vision fallback failed: {e}")
                        try:
                            os.unlink(tmp_path)
                        except:
                            pass

        return merged_paras, avg_document_confidence


    def process_pdf_digital(self, doc) -> Tuple[List[Dict[str, Any]], float]:
        """Extracts text blocks directly from digital text PDF."""
        paragraphs = []
        para_idx = 1
        _fitz = _ensure_fitz()
        if not doc or not _fitz:
            return paragraphs, 0.50

        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("blocks")
            for b in blocks:
                if b[6] == 0:
                    raw_text = b[4].strip()
                    clean_text = sanitize_indic_text(raw_text)
                    if clean_text:
                        # Normalize internal newlines within a block to single space
                        normalized_text = re.sub(r'\s+', ' ', clean_text).strip()
                        if normalized_text:
                            p_obj = {
                                "paragraph": para_idx,
                                "page": page_num + 1,
                                "text": normalized_text,
                                "confidence": 0.98
                            }
                            paragraphs.append(p_obj)
                            logger.info(f"[OCR OUTPUT - Digital PDF] Page {page_num+1} Para {para_idx} (Conf: 0.98): '{normalized_text}'")
                            para_idx += 1
        return paragraphs, 0.98

ocr_engine = OCRService()

