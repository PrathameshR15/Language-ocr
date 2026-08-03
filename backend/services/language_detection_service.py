import os
import re
import time
import requests
from typing import Dict, Tuple, Optional, Any

from backend.utils.logger import logger

try:
    import fasttext
    # Silence fasttext warning logs
    fasttext.FastText.eprint = lambda x: None
except (ImportError, Exception):
    fasttext = None


# Script Unicode Range Definitions
UNICODE_RANGES = {
    "Devanagari": (0x0900, 0x097F),
    "Bengali_Assamese": (0x0980, 0x09FF),
    "Gurmukhi": (0x0A00, 0x0A7F),
    "Gujarati": (0x0A80, 0x0AFF),
    "Odia": (0x0B00, 0x0B7F),
    "Tamil": (0x0B80, 0x0BFF),
    "Telugu": (0x0C00, 0x0C7F),
    "Kannada": (0x0C80, 0x0CFF),
    "Malayalam": (0x0D00, 0x0D7F),
    "Arabic_Urdu": (0x0600, 0x06FF),
    "Cyrillic": (0x0400, 0x04FF),
    "CJK": (0x4E00, 0x9FFF),
    "Hiragana_Katakana": (0x3040, 0x30FF),
    "Hangul": (0xAC00, 0xD7AF),
    "Thai": (0x0E00, 0x0E7F),
    "Latin": (0x0041, 0x007A) # Standard ASCII letters
}

GTX_LANG_CODE_MAP = {
    "en": "English", "hi": "Hindi", "mr": "Marathi", "gu": "Gujarati", "ta": "Tamil", "te": "Telugu",
    "kn": "Kannada", "ml": "Malayalam", "bn": "Bengali", "pa": "Punjabi", "or": "Odia",
    "ur": "Urdu", "fr": "French", "es": "Spanish", "de": "German", "zh-CN": "Chinese",
    "zh-TW": "Chinese", "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "ar": "Arabic",
    "ru": "Russian", "pt": "Portuguese", "it": "Italian", "tr": "Turkish", "nl": "Dutch",
    "fa": "Persian", "ne": "Nepali", "sa": "Sanskrit", "si": "Sinhala", "th": "Thai", "vi": "Vietnamese"
}

# Distinguishing keywords for Devanagari script languages
MARATHI_KEYWORDS = {
    "आहे", "आहेत", "शासन", "परिपत्रक", "ग्रामपंचायत", "निवडणूक", "तालुका", "जिल्हा", 
    "महाराष्ट्र", "यांचे", "करणे", "येईल", "विभाग", "नगरपालिका", "न्यायालय", "जमीन", 
    "सातबारा", "करण्यात", "येते", "होणार", "नागरिकांना", "सर्व", "या", "आणि", "व", "साठी", "बाबत", "अनुसार",
    "अहवाल", "विकास", "हा", "प्रगती"
}

HINDI_KEYWORDS = {
    "है", "हैं", "शासन", "सूचना", "चुनाव", "तहसील", "जिला", "उत्तर", "प्रदेश", 
    "बिहार", "का", "की", "के", "द्वारा", "विभाग", "न्यायालय", "भूमि", "पंचायत", "संसद"
}
NEPALI_KEYWORDS = {"छ", "छन्", "नेपाल", "सरकार", "लाई", "भएको", "विकास", "जिल्ला"}
SANSKRIT_KEYWORDS = {"अस्ति", "भवति", "तथा", "इति", "नमः", "सर्वत्र", "श्री", "राज्यम्"}
BHOJPURI_KEYWORDS = {"बा", "बानि", "रउरा", "लोगन", "खातिर", "हमर"}

ASSAMESE_KEYWORDS = {"অসম", "হৈছে", "নহয়", "দিয়ে"}
BENGALI_KEYWORDS = {"পশ্চিমবঙ্গ", "হচ্ছে", "জন্য", "বাংলাদেশ", "এবং"}

class LanguageDetectionService:
    """Paragraph-wise multi-lingual language detection for Indian & Global languages."""

    gtx_disabled_until: float = 0.0
    _fasttext_model = None

    @classmethod
    def get_fasttext_model(cls):
        """Lazy-loads local fastText lid.176.bin model."""
        if cls._fasttext_model is None and fasttext is not None:
            model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "lid.176.bin")
            if not os.path.exists(model_path):
                model_path = os.path.join("data", "lid.176.bin")

            if os.path.exists(model_path):
                try:
                    logger.info(f"Loading fastText pretrained language model from {model_path}...")
                    cls._fasttext_model = fasttext.load_model(model_path)
                    logger.info("fastText pretrained language detection model loaded successfully.")
                except Exception as e:
                    logger.warning(f"Failed to load fastText model from {model_path}: {e}")
                    cls._fasttext_model = None
        return cls._fasttext_model

    @classmethod
    def detect_via_fasttext(cls, text: str) -> Optional[Tuple[str, float]]:
        """Detect language using local fastText lid.176.bin pretrained model."""
        model = cls.get_fasttext_model()
        if not model or not text or not text.strip():
            return None
        try:
            clean = text.replace("\n", " ").strip()[:500]
            try:
                labels, confs = model.predict([clean], k=1)
                lbl = labels[0][0] if labels and len(labels) > 0 and len(labels[0]) > 0 else None
                cnf = float(confs[0][0]) if confs and len(confs) > 0 else 0.90
            except Exception:
                labels, confs = model.predict(clean, k=1)
                lbl = labels[0] if labels else None
                cnf = float(confs[0]) if confs is not None else 0.90

            if lbl:
                code = str(lbl).replace("__label__", "").lower()
                lang = GTX_LANG_CODE_MAP.get(code, code.capitalize())
                return lang, float(cnf)
        except Exception as e:
            logger.warning(f"fastText prediction error: {e}")
        return None


    @classmethod
    def detect_via_gtx(cls, text: str) -> Optional[str]:
        """Detect language code via Google GTX API."""
        now = time.time()
        if now <= cls.gtx_disabled_until:
            return None
        try:
            url = "https://translate.googleapis.com/translate_a/single"
            params = {"client": "gtx", "sl": "auto", "tl": "en", "dt": "t", "q": text[:300]}
            res = requests.get(url, params=params, timeout=1.5)
            if res.status_code == 200:
                data = res.json()
                if len(data) >= 3 and isinstance(data[2], str):
                    code = data[2].lower()
                    return GTX_LANG_CODE_MAP.get(code, code.capitalize())
            elif res.status_code == 429:
                cls.gtx_disabled_until = now + 300.0
        except Exception:
            cls.gtx_disabled_until = now + 120.0
        return None


    @classmethod
    def detect_language(cls, text: str) -> str:
        """Detect language of a given paragraph string automatically."""
        if not text or not text.strip():
            return "English"

        clean_text = text.strip()
        script_counts: Dict[str, int] = {}
        total_chars = 0

        for char in clean_text:
            code = ord(char)
            # Skip spaces and numbers
            if char.isspace() or char.isdigit() or not char.isalnum():
                continue
            
            total_chars += 1
            for script_name, (start, end) in UNICODE_RANGES.items():
                if start <= code <= end:
                    script_counts[script_name] = script_counts.get(script_name, 0) + 1
                    break

        if total_chars == 0:
            return "English"

        # Special check for Japanese: Hiragana/Katakana explicitly marks Japanese even when combined with CJK (Kanji)
        if script_counts.get("Hiragana_Katakana", 0) > 0:
            return "Japanese"

        # Determine dominant script
        dominant_script = max(script_counts, key=script_counts.get) if script_counts else "Latin"

        # Map Script to specific language
        if dominant_script == "Gujarati":
            return "Gujarati"
        elif dominant_script == "Gurmukhi":
            return "Punjabi"
        elif dominant_script == "Tamil":
            return "Tamil"
        elif dominant_script == "Telugu":
            return "Telugu"
        elif dominant_script == "Kannada":
            return "Kannada"
        elif dominant_script == "Malayalam":
            return "Malayalam"
        elif dominant_script == "Odia":
            return "Odia"
        elif dominant_script == "Arabic_Urdu":
            return "Urdu"
        elif dominant_script == "Cyrillic":
            return "Russian"
        elif dominant_script == "CJK":
            return "Chinese"
        elif dominant_script == "Hiragana_Katakana":
            return "Japanese"
        elif dominant_script == "Hangul":
            return "Korean"
        elif dominant_script == "Thai":
            return "Thai"
        elif dominant_script == "Bengali_Assamese":
            words = set(clean_text.split())
            if words.intersection(ASSAMESE_KEYWORDS) or "ৰ" in clean_text or "ৱ" in clean_text:
                return "Assamese"
        elif dominant_script == "Devanagari":
            words = set(clean_text.split())
            marathi_score = len(words.intersection(MARATHI_KEYWORDS)) + (2 if "ळ" in clean_text else 0)
            hindi_score = len(words.intersection(HINDI_KEYWORDS))
            nepali_score = len(words.intersection(NEPALI_KEYWORDS))
            sanskrit_score = len(words.intersection(SANSKRIT_KEYWORDS)) + (2 if "ः" in clean_text else 0)
            bhojpuri_score = len(words.intersection(BHOJPURI_KEYWORDS))

            scores = {
                "Hindi": hindi_score,
                "Marathi": marathi_score,
                "Nepali": nepali_score,
                "Sanskrit": sanskrit_score,
                "Bhojpuri": bhojpuri_score
            }

            max_lang = max(scores, key=scores.get)
            if scores[max_lang] > 0:
                return max_lang
            return "Hindi"

        # For Latin script or non-matched scripts, try GTX auto-detect for European/Global languages
        gtx_lang = cls.detect_via_gtx(clean_text)
        if gtx_lang:
            return gtx_lang

        return "English"

    @classmethod
    def detect_language_with_confidence(cls, text: str) -> Tuple[str, float]:
        """Detect language of text and return tuple of (Language, Confidence Score 0.0-1.0)."""
        if not text or not text.strip():
            return "English", 1.00

        clean_text = text.strip()
        script_counts: Dict[str, int] = {}
        total_chars = 0

        for char in clean_text:
            code = ord(char)
            if char.isspace() or char.isdigit() or not char.isalnum():
                continue
            
            total_chars += 1
            for script_name, (start, end) in UNICODE_RANGES.items():
                if start <= code <= end:
                    script_counts[script_name] = script_counts.get(script_name, 0) + 1
                    break

        if total_chars == 0:
            return "English", 1.00

        if script_counts.get("Hiragana_Katakana", 0) > 0:
            return "Japanese", 0.99

        dominant_script = max(script_counts, key=script_counts.get) if script_counts else "Latin"
        script_ratio = script_counts.get(dominant_script, 0) / total_chars

        # Direct script maps
        script_map = {
            "Gujarati": "Gujarati",
            "Gurmukhi": "Punjabi",
            "Tamil": "Tamil",
            "Telugu": "Telugu",
            "Kannada": "Kannada",
            "Malayalam": "Malayalam",
            "Odia": "Odia",
            "Arabic_Urdu": "Urdu",
            "Cyrillic": "Russian",
            "CJK": "Chinese",
            "Hiragana_Katakana": "Japanese",
            "Hangul": "Korean",
            "Thai": "Thai"
        }

        if dominant_script in script_map:
            conf = min(0.99, max(0.85, script_ratio))
            return script_map[dominant_script], round(conf, 2)

        # Strip punctuation from words for set matching
        raw_words = clean_text.split()
        clean_words = {re.sub(r'^[^\w]+|[^\w]+$', '', w, flags=re.UNICODE) for w in raw_words}
        clean_words.discard('')

        if dominant_script == "Bengali_Assamese":
            if clean_words.intersection(ASSAMESE_KEYWORDS) or "ৰ" in clean_text or "ৱ" in clean_text:
                return "Assamese", 0.98
            return "Bengali", 0.98

        elif dominant_script == "Devanagari":
            marathi_score = len(clean_words.intersection(MARATHI_KEYWORDS)) + (2 if "ळ" in clean_text else 0)
            hindi_score = len(clean_words.intersection(HINDI_KEYWORDS))
            nepali_score = len(clean_words.intersection(NEPALI_KEYWORDS))
            sanskrit_score = len(clean_words.intersection(SANSKRIT_KEYWORDS)) + (2 if "ः" in clean_text else 0)
            bhojpuri_score = len(clean_words.intersection(BHOJPURI_KEYWORDS))

            scores = {
                "Hindi": hindi_score,
                "Marathi": marathi_score,
                "Nepali": nepali_score,
                "Sanskrit": sanskrit_score,
                "Bhojpuri": bhojpuri_score
            }

            max_lang = max(scores, key=scores.get)
            if scores[max_lang] > 0:
                return max_lang, 0.98
            return "Hindi", 0.92

        # Local fastText pretrained model (100% offline, 176 languages)
        ft_res = cls.detect_via_fasttext(clean_text)
        if ft_res:
            ft_lang, ft_conf = ft_res
            if ft_conf >= 0.35:
                return ft_lang, round(min(0.99, max(0.85, ft_conf)), 2)

        gtx_lang = cls.detect_via_gtx(clean_text)
        if gtx_lang:
            return gtx_lang, 0.95

        return "English", 0.90


    @classmethod
    def detect_language_details(cls, text: str) -> Dict[str, Any]:
        """Detect language and return complete metadata (language, confidence, script, language_probability)."""
        lang, conf = cls.detect_language_with_confidence(text)
        
        # Determine script name
        script = "Latin"
        if text:
            for char in text.strip()[:100]:
                code = ord(char)
                for script_name, (start, end) in UNICODE_RANGES.items():
                    if start <= code <= end:
                        script = script_name
                        break

        return {
            "language": lang,
            "confidence": conf,
            "script": script,
            "language_probability": conf
        }

    @classmethod
    def detect_language(cls, text: str) -> str:
        """Detect language string (backward compatible)."""
        lang, _ = cls.detect_language_with_confidence(text)
        return lang



