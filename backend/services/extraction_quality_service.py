import re
from typing import Dict, Any
from config import settings
from backend.utils.logger import logger
from backend.services.language_detection_service import language_detector

class ExtractionQualityService:
    """Centralized quality scoring for digital text and OCR extraction."""

    def __init__(self):
        self.pass_threshold = getattr(settings, "QUALITY_PASS_THRESHOLD", 75)
        self.warn_threshold = getattr(settings, "QUALITY_WARN_THRESHOLD", 50)
        self.fail_threshold = getattr(settings, "QUALITY_FAIL_THRESHOLD", 25)

    def score_extraction(self, text: str, source_engine: str, base_confidence: float = 1.0) -> Dict[str, Any]:
        """
        Scores the extracted text quality from 0 to 100 based on multiple heuristics.
        Returns a structured dictionary with the score, status, reasons, and source.
        """
        if not text or not text.strip():
            return {
                "score": 0,
                "status": "fail",
                "reasons": ["Empty text"],
                "source": source_engine
            }

        score = base_confidence * 100.0
        reasons = []
        
        # 1. IPA/CMAP Noise Penalty
        ipa_noise_chars = re.findall(r'[ɟɹɷɡɞɶʞɰɱɲɳɴɵɸɺɻɼɽɾɿʀʁʂʃʄʅʆʇʈʉʊʋʌʍʎʏʐʑʒʓʔʕʖʗʘʙʚʛʜʝʟʠʡʢʣʤʥʦʧʨÇ]', text)
        if ipa_noise_chars:
            penalty = min(30, len(ipa_noise_chars) * 5)
            score -= penalty
            reasons.append(f"CMAP corruption: {len(ipa_noise_chars)} IPA noise glyphs detected")

        # 2. Replacement/Missing Characters Penalty
        missing_chars = re.findall(r'[■□\ufffdǂǬ]', text)
        if missing_chars:
            penalty = min(25, len(missing_chars) * 5)
            score -= penalty
            reasons.append(f"Missing glyphs: {len(missing_chars)} corrupted characters detected")

        # 3. Repeated Characters Anomaly (e.g., '????', '====')
        if re.search(r'([?=\-#*])\1{4,}', text):
            score -= 10
            reasons.append("Character repetition anomaly detected")

        # 4. Stray/Broken Devanagari/Bengali
        # Check for digits embedded inside words (e.g., अध्3ापन)
        embedded_digits = re.findall(r'[\u0900-\u097F\u0980-\u09FF]\d[\u0900-\u097F\u0980-\u09FF]', text)
        if embedded_digits:
            penalty = min(20, len(embedded_digits) * 5)
            score -= penalty
            reasons.append(f"Broken words: {len(embedded_digits)} embedded digits in Indic words")
            
        # 5. Length ratio checks
        total_len = len(text)
        indic_chars = len(re.findall(r'[\u0900-\u0D7F]', text))
        ascii_chars = len(re.findall(r'[a-zA-Z]', text))
        
        # If it claims to have Indic text but it's heavily overwhelmed by random ASCII
        if indic_chars > 0 and ascii_chars > indic_chars * 2:
             score -= 15
             reasons.append(f"Script anomaly: Disproportionate ASCII chars in Indic text ({ascii_chars} vs {indic_chars})")

        # Final score bound
        score = max(0, min(100, score))
        
        # Determine status
        if score >= self.pass_threshold:
            status = "pass"
        elif score >= self.fail_threshold:
            status = "warning"
        else:
            status = "fail"

        return {
            "score": round(score, 1),
            "status": status,
            "reasons": reasons,
            "source": source_engine
        }

extraction_quality_service = ExtractionQualityService()
