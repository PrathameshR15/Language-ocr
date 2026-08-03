import os
import re
from typing import List, Dict, Any, Tuple
from backend.utils.logger import logger

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

class LayoutParserService:
    """Document Layout Detection and Structural Reading Order Parser.
    Classifies text blocks into document components (Title, Office Address, Headings, Numbered Lists, Body, Signatures).
    """

    _yolo_model = None

    @classmethod
    def get_doclayout_yolo_model(cls):
        """Lazy-loads DocLayout-YOLO pretrained visual layout detection model."""
        if cls._yolo_model is None and YOLO is not None:
            model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "doclayout_yolo.pt")
            if not os.path.exists(model_path):
                model_path = os.path.join("data", "doclayout_yolo.pt")
            if not os.path.exists(model_path):
                model_path = "yolov8n.pt"

            try:
                logger.info(f"Loading DocLayout-YOLO visual layout detection model ({model_path})...")
                cls._yolo_model = YOLO(model_path)
                logger.info("DocLayout-YOLO pretrained model loaded successfully.")
            except Exception as e:
                logger.warning(f"DocLayout-YOLO load failed: {e}")
                cls._yolo_model = None
        return cls._yolo_model

    @classmethod
    def detect_visual_layout_yolo(cls, cv_img) -> List[Dict[str, Any]]:
        """Performs ultra-fast visual layout detection using DocLayout-YOLO model."""
        model = cls.get_doclayout_yolo_model()
        if not model or cv_img is None:
            return []

        detections = []
        try:
            results = model(cv_img, verbose=False)
            if results and len(results) > 0:
                boxes = results[0].boxes
                names = model.names
                for box in boxes:
                    xyxy = box.xyxy[0].tolist()
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    class_name = names.get(cls_id, "paragraph").lower()

                    layout_type = "paragraph"
                    if "title" in class_name: layout_type = "title"
                    elif "head" in class_name: layout_type = "heading"
                    elif "table" in class_name: layout_type = "table"
                    elif "header" in class_name: layout_type = "header"
                    elif "footer" in class_name: layout_type = "footer"
                    elif "signature" in class_name or "sign" in class_name: layout_type = "signature"
                    elif "stamp" in class_name or "seal" in class_name: layout_type = "stamp"
                    elif "figure" in class_name or "image" in class_name: layout_type = "image"
                    elif "list" in class_name: layout_type = "numbered_list"

                    detections.append({
                        "layout_type": layout_type,
                        "bbox": [float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])],
                        "confidence": round(conf, 2)
                    })
        except Exception as e:
            logger.warning(f"DocLayout-YOLO visual detection error: {e}")

        return detections

    @classmethod
    def detect_table_transformer_layout(cls, pil_img) -> List[Dict[str, Any]]:
        """Performs visual table layout detection using Microsoft's Table Transformer (TATR) model."""
        try:
            from backend.services.table_transformer_service import table_transformer_service
            tables = table_transformer_service.detect_tables(pil_img)
            detections = []
            for tbl in tables:
                detections.append({
                    "layout_type": "table",
                    "bbox": tbl["bbox"],
                    "confidence": tbl["score"]
                })
            return detections
        except Exception as e:
            logger.warning(f"Table Transformer layout detection error: {e}")
            return []



    @staticmethod
    def classify_block_type(text: str, bbox: List[float], page_width: float, page_height: float) -> Tuple[str, Dict[str, Any]]:
        """Classifies a block based on position, font indicators, list patterns, and administrative keywords."""
        if not text:
            return "paragraph", {"bold": False, "align": "left", "indent": 0}

        txt = text.strip()
        x0, y0, x1, y1 = bbox[0], bbox[1], bbox[2], bbox[3]
        block_w = x1 - x0
        block_center_x = (x0 + x1) / 2.0
        rel_top = y0 / float(page_height) if page_height > 0 else 0.0

        props = {
            "bold": False,
            "align": "left",
            "indent": 0,
            "font_size": 10,
            "is_list": False,
            "list_prefix": ""
        }

        # Check alignment relative to page width
        if abs(block_center_x - (page_width / 2.0)) < (page_width * 0.15):
            props["align"] = "center"
        elif x0 > (page_width * 0.50):
            props["align"] = "right"
        else:
            props["align"] = "left"

        # 1. Office Address Block (top-right office address)
        if rel_top < 0.35 and (x0 > (page_width * 0.40) or props["align"] == "right"):
            if any(k in txt for k in ["कार्यालय", "मजला", "रस्ता", "पुणे", "फोन", "पिंन", "बी विंग", "Office", "Floor", "Building"]):
                return "office_address", props

        # 2. Document Title / Subtitle / Main Heading
        if (rel_top < 0.25 and props["align"] == "center") or any(k in txt for k in ["अंतिम निवाडा", "सार्वजनिक सूचना", "शासकीय राजपत्र", "अधिसूचना", "GOVERNMENT OF INDIA", "PUBLIC NOTICE"]):
            props["bold"] = True
            props["font_size"] = 14
            return "title", props

        # 3. Header Block (top margin)
        if rel_top < 0.03:
            return "header", props

        # 4. Footer Block (bottom margin)
        if rel_top > 0.95:
            return "footer", props


        if rel_top < 0.30 and len(txt) < 80 and props["align"] == "center":
            props["bold"] = True
            props["font_size"] = 12
            return "subtitle", props

        # 5. Section Heading (e.g. विषय :-, प्रस्तावना :- , वाचा :- , आदेश :- )
        heading_keywords = ["विषय :-", "विषय:", "प्रस्तावना :-", "प्रस्तावना:", "वाचा :-", "वाचा:", "तपशील :-", "तपशील:", "आदेश :-", "आदेश:"]
        if any(txt.startswith(k) or txt == k for k in heading_keywords) or (len(txt) < 40 and txt.endswith(":-")):
            props["bold"] = True
            props["font_size"] = 12
            return "heading", props

        # 6. Bullet & Numbered List Item detection
        if txt.startswith(("•", "o", "-", "*", "▪", "►", "–")):
            props["is_list"] = True
            props["list_prefix"] = txt[0]
            props["indent"] = int(x0 / 15.0)
            return "bullet_list", props

        list_match = re.match(r'^(?:[\(（]?[0-9\u0966-\u096F]{1,3}[\)\）\.]|[\(（]?[a-zA-Z\u0900-\u097F][\)\）\.]|[०-९\d]+\))\s*', txt)
        if list_match:
            props["is_list"] = True
            props["list_prefix"] = list_match.group(0).strip()
            props["indent"] = int(x0 / 15.0)
            return "numbered_list", props

        # 7. Signature / Stamp / Seal / Officer Designation Block (bottom of page)
        if rel_top > 0.65 and any(k in txt for k in ["जिल्हाधिकारी", "उपजिल्हाधिकारी", "अधिकारी", "न्यायाधीश", "स्वाक्षरी", "शिक्का", "Collector", "Magistrate", "Officer", "Signature", "Stamp", "Seal"]):
            props["bold"] = True
            props["align"] = "right"
            if any(k in txt for k in ["शिक्का", "Stamp", "Seal"]):
                return "stamp", props
            return "signature", props

        return "paragraph", props

    @staticmethod
    def parse_layout_elements(blocks: List[Dict[str, Any]], page_width: float = 595.0, page_height: float = 842.0) -> List[Dict[str, Any]]:
        """Parses and enriches every layout block with bounding box, width, height, page_num, and rotation."""
        layout_blocks = []
        for b in blocks:
            bbox = b.get("bbox", [0.0, 0.0, 100.0, 20.0])
            x0, y0, x1, y1 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
            w = round(max(0.0, x1 - x0), 2)
            h = round(max(0.0, y1 - y0), 2)
            
            b_type, props = LayoutParserService.classify_block_type(b.get("text", ""), bbox, page_width, page_height)
            
            layout_blocks.append({
                "block_type": b.get("block_type", b_type),
                "bbox": [x0, y0, x1, y1],
                "width": w,
                "height": h,
                "page": b.get("page", 1),
                "rotation": b.get("rotation_angle", 0.0),
                "text": b.get("text", ""),
                "translated_text": b.get("translated_text", ""),
                "confidence": b.get("confidence", 0.90),
                "props": props
            })
        return layout_blocks

    @staticmethod
    def detect_divider_lines(cv_img) -> List[Tuple[float, float, float, float]]:
        """Detects horizontal divider lines using OpenCV Hough Line Transform."""
        lines_list = []
        try:
            import cv2
            if len(cv_img.shape) == 3:
                gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = cv_img.copy()

            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLinesP(edges, 1, 3.14159 / 180, threshold=100, minLineLength=int(gray.shape[1] * 0.3), maxLineGap=10)

            if lines is not None:
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    # Filter horizontal lines
                    if abs(y1 - y2) < 5:
                        lines_list.append((float(x1), float(y1), float(x2), float(y2)))
        except Exception as e:
            logger.debug(f"Divider line detection skipped: {e}")
        return lines_list

layout_parser = LayoutParserService()

