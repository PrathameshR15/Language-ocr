import os
import base64
import time
from typing import Dict, Any, Optional
from config import settings
from backend.utils.logger import logger

class OpenAIVisionService:
    """Final premium fallback using OpenAI Vision for difficult OCR regions."""

    def __init__(self):
        self.api_key = getattr(settings, "OPENAI_API_KEY", "")
        self.enabled = getattr(settings, "ENABLE_OPENAI_VISION", False)
        self.model = getattr(settings, "OPENAI_VISION_MODEL", "gpt-4o-mini")
        self.disabled_until = 0.0

    def is_available(self) -> bool:
        return bool(self.enabled and self.api_key and time.time() > self.disabled_until)

    def extract_text_from_image(self, image_path: str, lang_hint: str = "Unknown") -> Optional[str]:
        """
        Extracts visible text exactly as it appears in the image. No translation.
        """
        if not self.is_available():
            return None

        if not os.path.exists(image_path):
            return None

        try:
            # We use requests if openai package is not guaranteed to be installed
            import requests
            
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            prompt = (
                "Extract visible text exactly from this document image. "
                "Preserve the original language. Do not translate. Do not summarize. "
                "Do not infer missing information. Do not correct names, numbers, dates, IDs, or addresses. "
                "Preserve table rows and columns if any. "
                f"The document may contain {lang_hint} text."
            )

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 1000
            }

            now = time.time()
            res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=20.0)
            
            if res.status_code == 200:
                data = res.json()
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"].strip()
            else:
                logger.warning(f"OpenAI Vision API returned {res.status_code}: {res.text}. Circuit breaker active for 5m.")
                self.disabled_until = now + 300.0
                
        except Exception as e:
            logger.warning(f"OpenAI Vision API call failed: {e}. Circuit breaker active for 5m.")
            self.disabled_until = time.time() + 300.0
            
        return None

openai_vision_service = OpenAIVisionService()
