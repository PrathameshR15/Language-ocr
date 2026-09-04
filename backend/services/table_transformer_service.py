import torch
# pyrefly: ignore [missing-import]
from PIL import Image
from typing import List, Dict, Any
from backend.utils.logger import logger

try:
    from transformers import TableTransformerForObjectDetection, AutoImageProcessor
    TRANSFORMERS_TABLE_AVAILABLE = True
except ImportError:
    TableTransformerForObjectDetection = None
    AutoImageProcessor = None
    TRANSFORMERS_TABLE_AVAILABLE = False


class TableTransformerService:
    """Service utilizing Microsoft's Table Transformer (TATR) models:
    - microsoft/table-transformer-detection (detect table bounding boxes)
    - microsoft/table-transformer-structure-recognition (extract table rows, columns, headers, cells)
    """

    _detection_processor = None
    _detection_model = None
    _structure_processor = None
    _structure_model = None

    @classmethod
    def load_detection_model(cls):
        """Lazy loads microsoft/table-transformer-detection model."""
        if not TRANSFORMERS_TABLE_AVAILABLE:
            logger.warning("transformers package or timm is not installed. Table Transformer disabled.")
            return False

        if cls._detection_model is None:
            try:
                model_id = "microsoft/table-transformer-detection"
                logger.info(f"Loading Table Transformer Detection model ({model_id})...")
                cls._detection_processor = AutoImageProcessor.from_pretrained(model_id)
                cls._detection_model = TableTransformerForObjectDetection.from_pretrained(model_id)
                cls._detection_model.eval()
                logger.info("Table Transformer Detection model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load Table Transformer Detection model: {e}")
                cls._detection_model = None
                cls._detection_processor = None
                return False
        return True

    @classmethod
    def load_structure_model(cls):
        """Lazy loads microsoft/table-transformer-structure-recognition model."""
        if not TRANSFORMERS_TABLE_AVAILABLE:
            return False

        if cls._structure_model is None:
            try:
                model_id = "microsoft/table-transformer-structure-recognition"
                logger.info(f"Loading Table Transformer Structure Recognition model ({model_id})...")
                cls._structure_processor = AutoImageProcessor.from_pretrained(model_id)
                cls._structure_model = TableTransformerForObjectDetection.from_pretrained(model_id)
                cls._structure_model.eval()
                logger.info("Table Transformer Structure Recognition model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load Table Transformer Structure model: {e}")
                cls._structure_model = None
                cls._structure_processor = None
                return False
        return True

    @classmethod
    def detect_tables(cls, pil_img: Image.Image, threshold: float = 0.60) -> List[Dict[str, Any]]:
        """Detects tables in document image using Table Transformer Detection model.
        Returns list of dicts with 'bbox': [x0, y0, x1, y1], 'score': float, 'label': str.
        """
        if not cls.load_detection_model() or cls._detection_model is None or pil_img is None:
            return []

        try:
            img = pil_img.convert("RGB")
            inputs = cls._detection_processor(images=img, return_tensors="pt")
            
            with torch.no_grad():
                outputs = cls._detection_model(**inputs)

            target_sizes = torch.tensor([img.size[::-1]])
            results = cls._detection_processor.post_process_object_detection(
                outputs, threshold=threshold, target_sizes=target_sizes
            )[0]

            detected_tables = []
            for score, label, box in zip(results["scores"], results["labels"], results["boxes"]):
                box_list = [round(i, 2) for i in box.tolist()]
                score_val = round(score.item(), 3)
                label_name = cls._detection_model.config.id2label[label.item()]

                detected_tables.append({
                    "bbox": box_list,
                    "score": score_val,
                    "label": label_name
                })
            
            logger.info(f"Table Transformer detected {len(detected_tables)} table(s) in image.")
            return detected_tables
        except Exception as e:
            logger.error(f"Error during Table Transformer table detection: {e}")
            return []

    @classmethod
    def recognize_structure(cls, table_crop_img: Image.Image, threshold: float = 0.50) -> Dict[str, List[Dict[str, Any]]]:
        """Recognizes structural components (rows, columns, headers, cells) in a cropped table image.
        Returns dict with keys: 'rows', 'columns', 'headers', 'cells'.
        """
        if not cls.load_structure_model() or cls._structure_model is None or table_crop_img is None:
            return {"rows": [], "columns": [], "headers": [], "cells": []}

        try:
            img = table_crop_img.convert("RGB")
            inputs = cls._structure_processor(images=img, return_tensors="pt")

            with torch.no_grad():
                outputs = cls._structure_model(**inputs)

            target_sizes = torch.tensor([img.size[::-1]])
            results = cls._structure_processor.post_process_object_detection(
                outputs, threshold=threshold, target_sizes=target_sizes
            )[0]

            structure = {"rows": [], "columns": [], "headers": [], "cells": []}
            for score, label, box in zip(results["scores"], results["labels"], results["boxes"]):
                box_list = [round(i, 2) for i in box.tolist()]
                score_val = round(score.item(), 3)
                label_name = cls._structure_model.config.id2label[label.item()].lower()

                item = {"bbox": box_list, "score": score_val, "label": label_name}
                if "row" in label_name:
                    structure["rows"].append(item)
                elif "column" in label_name:
                    structure["columns"].append(item)
                elif "header" in label_name:
                    structure["headers"].append(item)
                else:
                    structure["cells"].append(item)

            # Sort rows top-to-bottom, columns left-to-right
            structure["rows"].sort(key=lambda r: r["bbox"][1])
            structure["columns"].sort(key=lambda c: c["bbox"][0])

            return structure
        except Exception as e:
            logger.error(f"Error during Table Transformer structure recognition: {e}")
            return {"rows": [], "columns": [], "headers": [], "cells": []}

    @classmethod
    def reconstruct_table(cls, pil_img: Image.Image, ocr_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detects tables and maps OCR text blocks into structured row/column grid tables.
        
        Args:
            pil_img: Page PIL Image
            ocr_blocks: List of OCR text dicts containing 'text' and 'bbox' ([x0, y0, x1, y1])

        Returns:
            List of reconstructed table objects with 'bbox', 'grid', 'markdown', 'html' representation.
        """
        detected_tables = cls.detect_tables(pil_img)
        if not detected_tables:
            return []

        reconstructed_results = []
        w, h = pil_img.size

        for idx, tbl in enumerate(detected_tables, start=1):
            tx0, ty0, tx1, ty1 = tbl["bbox"]

            # Crop table image
            crop_box = (max(0, int(tx0)), max(0, int(ty0)), min(w, int(tx1)), min(h, int(ty1)))
            if crop_box[2] <= crop_box[0] or crop_box[3] <= crop_box[1]:
                continue

            crop_img = pil_img.crop(crop_box)
            structure = cls.recognize_structure(crop_img)

            rows = structure["rows"]
            cols = structure["columns"]

            # Convert row/col bboxes back to full image coordinates
            for r in rows:
                r["bbox"] = [r["bbox"][0] + tx0, r["bbox"][1] + ty0, r["bbox"][2] + tx0, r["bbox"][3] + ty0]
            for c in cols:
                c["bbox"] = [c["bbox"][0] + tx0, c["bbox"][1] + ty0, c["bbox"][2] + tx0, c["bbox"][3] + ty0]

            # Filter OCR blocks belonging to this table
            tbl_ocr_words = []
            for block in ocr_blocks:
                bx0, by0, bx1, by1 = block.get("bbox", [0, 0, 0, 0])
                if not block.get("text", "").strip():
                    continue
                # Overlap check
                cx, cy = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0
                if tx0 <= cx <= tx1 and ty0 <= cy <= ty1:
                    tbl_ocr_words.append(block)

            if not tbl_ocr_words:
                continue

            # Fallback row/column grouping if Table Transformer didn't return explicit rows/cols
            if not rows:
                # Group words into rows based on Y-coordinates
                tbl_ocr_words_sorted = sorted(tbl_ocr_words, key=lambda b: b["bbox"][1])
                row_groups = []
                for b in tbl_ocr_words_sorted:
                    if not row_groups or abs(b["bbox"][1] - row_groups[-1][0]["bbox"][1]) > 15:
                        row_groups.append([b])
                    else:
                        row_groups[-1].append(b)
                
                rows = []
                for rg in row_groups:
                    ry0 = min(b["bbox"][1] for b in rg)
                    ry1 = max(b["bbox"][3] for b in rg)
                    rows.append({"bbox": [tx0, ry0, tx1, ry1]})

            if not cols:
                # Group words into columns based on X-coordinates
                col_centers = sorted(set([(b["bbox"][0] + b["bbox"][2]) / 2.0 for b in tbl_ocr_words]))
                cols = []
                last_x = None
                for xc in col_centers:
                    if last_x is None or abs(xc - last_x) > 40:
                        cols.append({"bbox": [xc - 30, ty0, xc + 30, ty1]})
                        last_x = xc

            # Build 2D Grid
            grid = [["" for _ in range(max(1, len(cols)))] for _ in range(max(1, len(rows)))]

            for block in tbl_ocr_words:
                bx0, by0, bx1, by1 = block.get("bbox", [0, 0, 0, 0])
                bcx, bcy = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0

                # Find best matching row and column index
                best_r = 0
                min_r_dist = float("inf")
                for r_idx, r in enumerate(rows):
                    ry0, ry1 = r["bbox"][1], r["bbox"][3]
                    dist = abs(bcy - (ry0 + ry1) / 2.0)
                    if dist < min_r_dist:
                        min_r_dist = dist
                        best_r = r_idx

                best_c = 0
                min_c_dist = float("inf")
                for c_idx, c in enumerate(cols):
                    cx0, cx1 = c["bbox"][0], c["bbox"][2]
                    dist = abs(bcx - (cx0 + cx1) / 2.0)
                    if dist < min_c_dist:
                        min_c_dist = dist
                        best_c = c_idx

                existing_text = grid[best_r][best_c]
                new_text = block["text"].strip()
                if existing_text:
                    grid[best_r][best_c] = f"{existing_text} {new_text}"
                else:
                    grid[best_r][best_c] = new_text

            # Generate Markdown table
            md_lines = []
            if grid:
                header = grid[0]
                md_lines.append("| " + " | ".join(header) + " |")
                md_lines.append("| " + " | ".join(["---"] * len(header)) + " |")
                for row in grid[1:]:
                    md_lines.append("| " + " | ".join(row) + " |")
            markdown_table = "\n".join(md_lines)

            # Generate HTML table
            html_rows = []
            for r_idx, row in enumerate(grid):
                tag = "th" if r_idx == 0 else "td"
                cells_html = "".join([f"<{tag}>{cell}</{tag}>" for cell in row])
                html_rows.append(f"<tr>{cells_html}</tr>")
            html_table = f"<table border='1'>\n" + "\n".join(html_rows) + "\n</table>"

            reconstructed_results.append({
                "table_index": idx,
                "bbox": [tx0, ty0, tx1, ty1],
                "confidence": tbl["score"],
                "grid": grid,
                "markdown": markdown_table,
                "html": html_table
            })

        return reconstructed_results


table_transformer_service = TableTransformerService()
