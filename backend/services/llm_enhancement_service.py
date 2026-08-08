import os
import json
import requests
from typing import Dict, Any, Optional, List
from config import settings
from backend.utils.logger import logger

import time

class LLMEnhancementService:
    """Optional LLM integration (Gemini / Groq) for high-accuracy translation, metadata extraction, and classification."""

    def __init__(self):
        self.gemini_key = (settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")).strip()
        self.groq_key = (settings.GROQ_API_KEY or os.environ.get("GROQ_API_KEY", "")).strip()
        self.gemini_disabled_until = 0.0
        self.groq_disabled_until = 0.0

    def is_available(self) -> bool:
        now = time.time()
        gemini_ok = bool(self.gemini_key) and now > self.gemini_disabled_until
        groq_ok = bool(self.groq_key) and now > self.groq_disabled_until
        return gemini_ok or groq_ok

    def extract_metadata_llm(self, text: str) -> Optional[Dict[str, Any]]:
        """Uses LLM to perform zero-shot extraction of structured document metadata for any document type."""
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

        now = time.time()
        # Try Gemini API first
        if self.gemini_key and now > self.gemini_disabled_until:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={self.gemini_key}"
                headers = {"Content-Type": "application/json"}
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                res = requests.post(url, json=payload, headers=headers, timeout=1.5)
                if res.status_code == 200:
                    resp_json = res.json()
                    candidates = resp_json.get("candidates", [])
                    if candidates:
                        raw_reply = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        json_match = raw_reply.strip()
                        if "```json" in json_match:
                            json_match = json_match.split("```json")[1].split("```")[0].strip()
                        elif "```" in json_match:
                            json_match = json_match.split("```")[1].strip()
                        return json.loads(json_match)
                else:
                    self.gemini_disabled_until = now + 3600.0
                    logger.warning(f"Gemini API returned status {res.status_code}. Disabling Gemini for 1hr.")
            except Exception as e:
                self.gemini_disabled_until = now + 3600.0
                logger.warning(f"Gemini LLM metadata extraction failed/timed out: {e}. Disabling Gemini for 1hr.")

        # Try Groq API as fallback
        if self.groq_key and now > self.groq_disabled_until:
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self.groq_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"}
                }
                res = requests.post(url, json=payload, headers=headers, timeout=1.5)
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    return json.loads(content)
                else:
                    self.groq_disabled_until = now + 3600.0
                    logger.warning(f"Groq API returned status {res.status_code}. Disabling Groq for 1hr.")
            except Exception as e:
                self.groq_disabled_until = now + 3600.0
                logger.warning(f"Groq LLM metadata extraction failed/timed out: {e}. Disabling Groq for 1hr.")

        return None

    def translate_paragraph_llm(self, text: str, source_lang: str) -> Optional[str]:
        """Translates regional language text to clear English using LLM."""
        if not self.is_available() or source_lang.lower() == "english":
            return text

        prompt = f"""You are a professional universal document translator.

Translate the following document or text into clear, formal English.

Rules:
- Preserve original meaning, idioms, sayings, and context.
- Never summarize or omit any content.
- Accept and translate ANY document type (general text, personal letters, business contracts, legal documents, technical reports, literature, idioms, government forms, certificates, invoices, etc.).
- NEVER refuse a translation or claim that the input is not a valid document or not a government document. Translate whatever text or proverb is provided.
- Preserve formatting, numbers, dates, lists, tables, and headings.
- Return ONLY the clean, translated text. Do not add meta-disclaimers, refusal notes, or commentary.

DOCUMENT TEXT:
{text}"""


        now = time.time()
        if self.gemini_key and now > self.gemini_disabled_until:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={self.gemini_key}"
                headers = {"Content-Type": "application/json"}
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                res = requests.post(url, json=payload, headers=headers, timeout=1.0)
                if res.status_code == 200:
                    resp_json = res.json()
                    candidates = resp_json.get("candidates", [])
                    if candidates:
                        return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                else:
                    self.gemini_disabled_until = now + 3600.0
                    logger.warning(f"Gemini API status {res.status_code}. Circuit breaker active 1hr.")
            except Exception as e:
                self.gemini_disabled_until = now + 3600.0
                logger.warning(f"Gemini LLM translation failed: {e}. Circuit breaker active 1hr.")

        # Try Groq API as fallback
        if self.groq_key and now > self.groq_disabled_until:
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self.groq_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}]
                }
                res = requests.post(url, json=payload, headers=headers, timeout=1.0)
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    self.groq_disabled_until = now + 3600.0
                    logger.warning(f"Groq API status {res.status_code}. Circuit breaker active 1hr.")
            except Exception as e:
                self.groq_disabled_until = now + 3600.0
                logger.warning(f"Groq LLM translation failed: {e}. Circuit breaker active 1hr.")

        return None

    def _call_llm_raw(self, prompt: str, timeout: float = 8.0) -> Optional[str]:
        """Generic LLM call helper returning raw text response from Gemini or Groq."""
        now = time.time()
        # Try Gemini API first
        if self.gemini_key and now > self.gemini_disabled_until:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
                headers = {"Content-Type": "application/json"}
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                res = requests.post(url, json=payload, headers=headers, timeout=timeout)
                if res.status_code == 200:
                    resp_json = res.json()
                    candidates = resp_json.get("candidates", [])
                    if candidates:
                        return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                else:
                    self.gemini_disabled_until = now + 300.0
                    logger.warning(f"Gemini API status {res.status_code}. Circuit breaker active 5min.")
            except Exception as e:
                self.gemini_disabled_until = now + 300.0
                logger.warning(f"Gemini LLM call failed: {e}. Circuit breaker active 5min.")

        # Try Groq API as fallback
        if self.groq_key and now > self.groq_disabled_until:
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self.groq_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}]
                }
                res = requests.post(url, json=payload, headers=headers, timeout=timeout)
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    self.groq_disabled_until = now + 300.0
                    logger.warning(f"Groq API status {res.status_code}. Circuit breaker active 5min.")
            except Exception as e:
                self.groq_disabled_until = now + 300.0
                logger.warning(f"Groq LLM call failed: {e}. Circuit breaker active 5min.")

        return None

    def correct_ocr_paragraphs_with_llm(self, paragraphs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Uses Gemini Flash / Groq LLM to perform zero-shot contextual OCR error correction
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

            raw_resp = self._call_llm_raw(prompt, timeout=8.0)
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
                    logger.warning(f"Failed to parse LLM OCR correction JSON response: {e}")

        updated_paragraphs = []
        for idx, p in enumerate(paragraphs):
            p_copy = dict(p)
            if idx in corrected_dict:
                orig_text = p_copy.get("text", "")
                llm_text = corrected_dict[idx]
                p_copy["text"] = llm_text
                p_copy["ocr_raw_text"] = orig_text
                logger.info(f"[LLM OCR CORRECTION] Para {idx+1}: '{orig_text}' -> '{llm_text}'")
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

        corrected = self._call_llm_raw(prompt, timeout=3.0)
        return corrected.strip() if corrected else text

    def generate_summary(self, text: str) -> str:
        """
        Generates a 100% accurate, comprehensive English summary of any document.
        """
        if not self.is_available() or not text or not text.strip():
            return "Summarization is unavailable because LLM keys are not configured or the text is empty."

        prompt = f"""You are a high-accuracy Document Intelligence AI.
Provide a clear, 100% accurate, and comprehensive executive summary of the following document in English.

Rules:
1. Ensure the summary is 100% accurate and contains only facts mentioned in the text.
2. Structure the summary logically (e.g., Key Purpose, Important Details/Actions, Names/Dates/Numbers).
3. Do not include external assumptions or introduce facts not in the document.
4. Keep the output clean, professional, and written in English.

DOCUMENT CONTENT:
{text[:8000]}
"""
        res = self._call_llm_raw(prompt, timeout=10.0)
        return res.strip() if res else "Failed to generate summary using LLM."

llm_service = LLMEnhancementService()

