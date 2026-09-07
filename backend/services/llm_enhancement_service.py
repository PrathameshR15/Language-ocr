import os
import json
import requests
from typing import Dict, Any, Optional, List
from config import settings
from backend.utils.logger import logger

import time

class LLMEnhancementService:
    """LLM integration using OpenAI (GPT-4o-mini) for translation, metadata extraction, and OCR correction."""

    def __init__(self):
        self.openai_key = (getattr(settings, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")).strip()
        self.openai_model = getattr(settings, "OPENAI_VISION_MODEL", "gpt-4o-mini")
        self.openai_disabled_until = 0.0

    def is_available(self) -> bool:
        return bool(self.openai_key) and time.time() > self.openai_disabled_until

    def _call_openai(self, prompt: str, timeout: float = 15.0, json_mode: bool = False) -> Optional[str]:
        """Generic OpenAI API call returning raw text response."""
        if not self.is_available():
            return None
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json"
            }
            payload: Dict[str, Any] = {
                "model": self.openai_model,
                "messages": [{"role": "user", "content": prompt}]
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}

            res = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                self.openai_disabled_until = time.time() + 300.0
                logger.warning(f"OpenAI API returned {res.status_code}. Circuit breaker active 5min.")
        except Exception as e:
            self.openai_disabled_until = time.time() + 300.0
            logger.warning(f"OpenAI API call failed: {e}. Circuit breaker active 5min.")
        return None

    def extract_metadata_llm(self, text: str) -> Optional[Dict[str, Any]]:
        """Uses OpenAI to extract structured document metadata."""
        if not self.is_available() or not text:
            return None

        prompt = f"""You are a Multilingual Document Intelligence AI. Extract metadata from the document text below. Return ONLY a valid JSON object matching these exact keys:
{{
  "state": "State / Region Name or N/A",
  "district": "District / City Name or N/A",
  "department": "Department / Organization / Ministry Name or N/A",
  "doc_number": "Document Number / ID or N/A",
  "reference_number": "Reference Number / File ID or N/A",
  "date": "Document Date or N/A",
  "issue_date": "Issue Date or N/A",
  "subject": "Subject / Title / Heading of document or N/A",
  "authority_name": "Authority / Publisher / Office Name or N/A",
  "officer_name": "Officer / Author / Signatory Name or N/A",
  "election_constituency": "Election Constituency / Ward or N/A",
  "polling_booth": "Polling Booth Name/No. or N/A",
  "village": "Village / Locality or N/A",
  "taluka": "Taluka / Sub-division / Suburb or N/A",
  "pin_code": "PIN Code / Postal Code or N/A",
  "phone_number": "Phone Number or N/A",
  "email": "Email Address or N/A",
  "website": "Website URL or N/A",
  "doc_category": "Category (e.g. Letter, Report, Certificate, Invoice, General, Contract, Notice, Circular, Land Record, Tax Bill)",
  "summary": "2-3 sentence summary of the document purpose"
}}

DOCUMENT TEXT:
{text[:4000]}
"""
        raw = self._call_openai(prompt, timeout=15.0, json_mode=True)
        if raw:
            try:
                cleaned = raw.strip()
                if "```json" in cleaned:
                    cleaned = cleaned.split("```json")[1].split("```")[0].strip()
                elif "```" in cleaned:
                    cleaned = cleaned.split("```")[1].strip()
                return json.loads(cleaned)
            except Exception as e:
                logger.warning(f"Failed to parse OpenAI metadata JSON: {e}")
        return None

    def translate_paragraph_llm(self, text: str, source_lang: str) -> Optional[str]:
        """Translates regional language text to clear English using OpenAI."""
        if not self.is_available() or source_lang.lower() == "english":
            return text

        prompt = f"""You are a professional universal document translator.

Translate the following document or text into clear, formal English.

Rules:
- Preserve original meaning, idioms, sayings, and context.
- Never summarize or omit any content.
- Accept and translate ANY document type (general text, personal letters, business contracts, legal documents, technical reports, literature, idioms, government forms, certificates, invoices, etc.).
- NEVER refuse a translation or claim that the input is not a valid document. Translate whatever text or proverb is provided.
- Preserve formatting, numbers, dates, lists, tables, and headings.
- Return ONLY the clean, translated text. Do not add meta-disclaimers, refusal notes, or commentary.

DOCUMENT TEXT:
{text}"""

        return self._call_openai(prompt, timeout=15.0)

    def _call_llm_raw(self, prompt: str, timeout: float = 8.0) -> Optional[str]:
        """Generic LLM call helper returning raw text response."""
        return self._call_openai(prompt, timeout=timeout)

    def correct_ocr_paragraphs_with_llm(self, paragraphs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Uses OpenAI to perform zero-shot contextual OCR error correction
        on raw extracted paragraphs BEFORE passing text to translation engine.
        Repairs corrupted Devanagari/Bengali matras, broken split halants, font artifacts, and OCR character typos.
        """
        import re
        if not self.is_available() or not paragraphs:
            return paragraphs

        items_to_correct = []
        for idx, p in enumerate(paragraphs):
            txt = p.get("text", "").strip()
            if txt and not p.get("table_grid") and len(txt) >= 3 and not txt.startswith("[TABLE GRID]"):
                items_to_correct.append({"id": idx, "text": txt})

        if not items_to_correct:
            return paragraphs

        batch_size = 15
        corrected_dict = {}

        for b_start in range(0, len(items_to_correct), batch_size):
            batch = items_to_correct[b_start:b_start + batch_size]
            prompt = """You are an expert Multilingual Preprocessing AI. Correct OCR character typos, corrupted Indic matras, split halants, and font encoding noise in the paragraphs below.

RULES:
1. Correct typos & broken matras (e.g. 'ऊजार्ट' -> 'ऊर्जा', 'पग्रɟत' -> 'प्रगति', 'सर्तिचाई' -> 'सिंचाई').
2. Return text IN THE ORIGINAL SOURCE LANGUAGE. Do NOT translate to English.
3. Keep numbers, dates, reference IDs, proper names (e.g. तळेघर, नाबार्ड), and punctuation intact.
4. Output ONLY a valid JSON array of objects with keys "id" and "corrected_text".

PARAGRAPHS TO CORRECT:
""" + json.dumps(batch, ensure_ascii=False, indent=2)

            raw_resp = self._call_llm_raw(prompt, timeout=20.0)
            if raw_resp:
                try:
                    cleaned_json_str = re.sub(r'^```(?:json)?\s*', '', raw_resp.strip(), flags=re.MULTILINE)
                    cleaned_json_str = re.sub(r'\s*```$', '', cleaned_json_str, flags=re.MULTILINE).strip()
                    resp_json = json.loads(cleaned_json_str)
                    if isinstance(resp_json, list):
                        for item in resp_json:
                            if isinstance(item, dict) and "id" in item and "corrected_text" in item:
                                p_id = item["id"]
                                c_text = str(item["corrected_text"]).strip()
                                if c_text and len(c_text) >= 2:
                                    corrected_dict[p_id] = c_text
                except Exception as e:
                    logger.warning(f"Failed to parse OpenAI OCR correction JSON response: {e}")

        updated_paragraphs = []
        for idx, p in enumerate(paragraphs):
            p_copy = dict(p)
            if idx in corrected_dict:
                orig_text = p_copy.get("text", "")
                llm_text = corrected_dict[idx]
                p_copy["text"] = llm_text
                p_copy["ocr_raw_text"] = orig_text
                logger.info(f"[OpenAI OCR CORRECTION] Para {idx+1}: '{orig_text[:60]}' -> '{llm_text[:60]}'")
            updated_paragraphs.append(p_copy)

        return updated_paragraphs

    def correct_english_translation(self, text: str) -> str:
        """
        Validates English translation grammar, flow, and removes any remaining box characters (■, □)
        or font-scrambled numbers.
        """
        if not self.is_available() or not text or not text.strip():
            return text

        prompt = f"""You are an expert English editor.
Review and validate the following English translation.
1. Correct any grammar issues, awkward phrasing, and flow.
2. Remove any leftover OCR artifacts or glyph boxes (like ■, □, ǂ, or ǃ).
3. Repair any font-corrupted digits or words (e.g., if you see "7Banyamu=ly", "7dati", "7Bashmukt" convert to their proper English meaning like "commercial", "days", "toxic-free").
4. Keep the output formal, clean, and direct.
5. Return ONLY the final corrected English text. Do not add metadata, comments, or explanations.

INPUT TEXT:
{text}"""

        corrected = self._call_openai(prompt, timeout=10.0)
        return corrected.strip() if corrected else text


llm_service = LLMEnhancementService()
