import threading
from typing import List, Dict, Any, Optional
from config import settings
from backend.utils.logger import logger

class NERService:
    """
    Generalist Named Entity Recognition (NER) Service powered by GLiNER.
    Provides zero-shot entity extraction for names, organizations, locations, etc.
    Guarantees non-blocking lazy loading and safe fallbacks.
    """
    _model = None
    _load_lock = threading.Lock()
    _failed_to_load = False

    @classmethod
    def _get_model(cls):
        """Lazy load GLiNER model thread-safely with error handling."""
        if not settings.ENABLE_GLINER:
            return None

        if cls._model is not None:
            return cls._model

        if cls._failed_to_load:
            return None

        with cls._load_lock:
            if cls._model is None and not cls._failed_to_load:
                try:
                    from gliner import GLiNER
                    model_name = getattr(settings, "GLINER_MODEL_NAME", "urchade/gliner_multi-v2.1")
                    logger.info(f"Loading GLiNER model '{model_name}' for zero-shot entity recognition...")
                    cls._model = GLiNER.from_pretrained(model_name)
                    logger.info(f"Successfully loaded GLiNER model '{model_name}'.")
                except Exception as e:
                    logger.warning(f"GLiNER model initialization note: {e}. Falling back to rule-based entity preservation.")
                    cls._failed_to_load = True
                    cls._model = None

        return cls._model

    @classmethod
    def extract_entities(
        cls,
        text: str,
        labels: Optional[List[str]] = None,
        threshold: float = 0.35
    ) -> List[Dict[str, Any]]:
        """
        Extract named entities (person, organization, location, etc.) from text using GLiNER.
        Returns a list of entity dictionaries containing 'text', 'label', 'start', 'end', and 'score'.
        """
        if not text or not text.strip():
            return []

        model = cls._get_model()
        if model is None:
            return []

        if labels is None:
            labels = getattr(settings, "GLINER_ENTITY_LABELS", ["person", "organization", "location", "facility"])

        try:
            entities = model.predict_entities(text, labels, threshold=threshold)
            return entities
        except Exception as e:
            logger.warning(f"Error during GLiNER entity extraction: {e}")
            return []

    @classmethod
    def extract_name_entities(cls, text: str) -> List[str]:
        """
        Extracts entity text strings specifically for person names, organizations, and locations
        to protect during translation. Filters duplicates while preserving longest entity spans.
        """
        entities = cls.extract_entities(text)
        if not entities:
            return []

        # Sort entities by length descending to prioritize longer phrases (e.g., "डॉ. शुभांगी गायकवाड")
        sorted_entities = sorted(entities, key=lambda x: len(x.get("text", "")), reverse=True)
        extracted_texts = []

        for ent in sorted_entities:
            ent_text = ent.get("text", "").strip()
            if ent_text and ent_text not in extracted_texts:
                extracted_texts.append(ent_text)

        return extracted_texts

ner_service = NERService()
