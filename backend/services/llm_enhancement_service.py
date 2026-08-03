import os
import json
import requests
from typing import Dict, Any, Optional
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

llm_service = LLMEnhancementService()

