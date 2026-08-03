import re
import numpy as np
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
            import fitz as _fitz
            fitz = _fitz
        except ImportError:
            pass
    return fitz

def _ensure_easyocr():
    global easyocr
    if easyocr is None:
        try:
            import easyocr as _easyocr
            easyocr = _easyocr
        except ImportError:
            pass
    return easyocr

def _ensure_paddleocr():
    global PaddleOCR
    if PaddleOCR is None:
        try:
            from paddleocr import PaddleOCR as _PaddleOCR
            PaddleOCR = _PaddleOCR
        except ImportError:
            pass
    return PaddleOCR

def _ensure_rapidocr():
    global RapidOCR
    if RapidOCR is None:
        try:
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
        """Lazy-loads EasyOCR reader with Devanagari (Hindi, Marathi) & English models with verbose=False for Windows compatibility."""
        _easyocr = _ensure_easyocr()
        if self._easyocr_reader is None and _easyocr is not None:
            for langs in [['hi', 'mr', 'en'], ['mr', 'en'], ['hi', 'en']]:
                try:
                    logger.info(f"Initializing EasyOCR reader for Indic models {langs}...")
                    self._easyocr_reader = _easyocr.Reader(langs, gpu=False, verbose=False)
                    logger.info(f"EasyOCR Indic reader loaded successfully ({langs}).")
                    break
                except Exception as e:
                    logger.warning(f"EasyOCR init failed for {langs}: {e}")
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
                    if tp.get("table_grid"):
                        for r in tp.get("table_grid"):
                            grid.append(r)
                    elif "|" in t_str:
                        cells = [c.strip() for c in t_str.split("|") if c.strip()]
                        if cells: grid.append(cells)
                    else:
                        cells = [c.strip() for c in re.split(r'\s{2,}|\t', t_str) if c.strip()]
                        if cells: grid.append(cells)

                if grid and len(grid) >= 2 and any(len(r) >= 2 for r in grid):
                    max_cols = max(len(r) for r in grid)
                    norm_grid = [r + [""] * (max_cols - len(r)) for r in grid]

                    # Compute combined bounding box for all table rows
                    all_bboxes = [tp.get("bbox") for tp in table_candidates if tp.get("bbox") and len(tp.get("bbox")) == 4]
                    combined_bbox = None
                    if all_bboxes:
                        min_x = min(b[0] for b in all_bboxes)
                        min_y = min(b[1] for b in all_bboxes)
                        max_x = max(b[2] for b in all_bboxes)
                        max_y = max(b[3] for b in all_bboxes)
                        combined_bbox = [min_x, min_y, max_x, max_y]

                    # Construct Markdown table string for text representation
                    orig_md_lines = []
                    if norm_grid:
                        orig_md_lines.append("| " + " | ".join(norm_grid[0]) + " |")
                        orig_md_lines.append("| " + " | ".join(["---"] * len(norm_grid[0])) + " |")
                        for r in norm_grid[1:]:
                            orig_md_lines.append("| " + " | ".join(r) + " |")

                    result_paras.append({
                        "paragraph": len(result_paras) + 1,
                        "page": table_candidates[0].get("page", 1),
                        "text": "\n".join(orig_md_lines),
                        "block_type": "table",
                        "table_grid": norm_grid,
                        "bbox": combined_bbox or table_candidates[0].get("bbox"),
                        "confidence": 0.99
                    })
                else:
                    result_paras.extend(table_candidates)
            else:
                result_paras.extend(table_candidates)
            table_candidates = []

        for p in paragraphs:
            txt = p.get("text", "").strip()
            cols = [c.strip() for c in re.split(r'\||\s{2,}|\t', txt) if c.strip()]

            is_tbl_row = False
            if p.get("block_type") == "table" or p.get("table_grid"):
                is_tbl_row = True
            elif len(cols) >= 2:
                is_tbl_row = True
            elif any(k in txt for k in [
                "उपक्रमाचे नाव", "वाक्यप्रचार", "साध्य व प्रगती", "ध्येय", "उपक्रमनिहाय", 
                "प्रगती तक्ता", "एकूण निष्कर्ष", "Activity Name", "Achievement", "Goal",
                "Progress", "Sr.", "No.", "तपशील", "कालावधी", "खर्च", "लाभार्थी"
            ]):
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
        paragraphs.sort(key=lambda p: (p.get("page", 1), p.get("bbox", [0, 0, 0, 0])[1] if p.get("bbox") else 0, p.get("bbox", [0, 0, 0, 0])[0] if p.get("bbox") else 0))

        # First pass: Auto-detect table grid lines
        paragraphs = cls.detect_table_grid_from_paragraphs(paragraphs)

        merged = []
        para_idx = 1

        for p in paragraphs:
            txt = p.get("text", "").strip()
            if not txt:
                continue

            if p.get("block_type") == "table" or p.get("table_grid"):
                p_copy = dict(p)
                p_copy["paragraph"] = para_idx
                merged.append(p_copy)
                para_idx += 1
                continue

            if merged:
                prev_text = merged[-1]["text"].strip()
                if merged[-1].get("block_type") != "table" and not re.search(r'[.\!\?\|:;:-]\s*$', prev_text) and not merged[-1].get("is_list") and not p.get("is_list"):
                    merged[-1]["text"] = f"{prev_text} {txt}".strip()
                    if "confidence" in p and "confidence" in merged[-1]:
                        merged[-1]["confidence"] = round((merged[-1]["confidence"] + p["confidence"]) / 2.0, 2)
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
                            if raw_grid:
                                for row in raw_grid:
                                    clean_row = [sanitize_indic_text(str(cell or "")) for cell in row]
                                    if any(clean_row):
                                        clean_grid.append(clean_row)

                            if clean_grid:
                                has_digital_text = True
                                table_bboxes.append(t_bbox)
                                page_paras.append({
                                    "paragraph": para_idx,
                                    "page": page_num,
                                    "text": "[TABLE GRID]",
                                    "table_grid": clean_grid,
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

    def process_image(self, pil_image: Image.Image, page_num: int = 1) -> Tuple[List[Dict[str, Any]], float]:
        """Runs image preprocessing, performs OCR extraction, validates output quality, and merges sentence fragments."""
        w, h = pil_image.size
        if max(w, h) > 1600:
            scale = 1600.0 / float(max(w, h))
            new_w, new_h = int(w * scale), int(h * scale)
            pil_image = pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)

        cv_img = ImagePreprocessingService.pil_to_cv2(pil_image)
        
        paragraphs = []
        confidences = []

        # 1. Primary Engine: RapidOCR (ultra-fast ONNX runtime engine < 0.1s)
        _engine = self._get_rapidocr()
        if _engine:
            try:
                results, _ = _engine(cv_img)
                if not results:
                    # Fallback to grayscale if raw color image returned no text boxes
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

        # 2. Fallback: PaddleOCR (if RapidOCR threw an exception)
        _PaddleOCR = _ensure_paddleocr()
        if _PaddleOCR is not None:
            paddle_paras, paddle_conf = self.process_image_paddleocr(cv_img, page_num)
            if paddle_paras:
                merged_paras = self.merge_ocr_line_fragments(paddle_paras)
                return merged_paras, paddle_conf

        avg_document_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.92
        merged_paras = self.merge_ocr_line_fragments(paragraphs)
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

